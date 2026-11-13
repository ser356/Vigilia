#include "VGPlayerCharacter.h"
#include "VGInteractionComponent.h"
#include "VGExaminable.h"
#include "VGStatics.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SpotLightComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Engine/LocalPlayer.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "InputModifiers.h"
#include "GameFramework/GameUserSettings.h"

AVGPlayerCharacter::AVGPlayerCharacter()
{
	PrimaryActorTick.bCanEverTick = true;

	// Persona de ~1,78 m con los ojos a ~1,65 m.
	GetCapsuleComponent()->InitCapsuleSize(30.f, 89.f);

	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(GetCapsuleComponent());
	Camera->SetRelativeLocation(FVector(0.f, 0.f, 76.f));
	Camera->bUsePawnControlRotation = true;
	Camera->SetFieldOfView(82.f);

	Flashlight = CreateDefaultSubobject<USpotLightComponent>(TEXT("Flashlight"));
	Flashlight->SetupAttachment(Camera);
	Flashlight->SetRelativeLocation(FVector(8.f, 14.f, -12.f));
	Flashlight->SetIntensityUnits(ELightUnits::Lumens);
	Flashlight->SetIntensity(90.f);
	Flashlight->SetInnerConeAngle(9.f);
	Flashlight->SetOuterConeAngle(24.f);
	Flashlight->SetAttenuationRadius(1100.f);
	Flashlight->bUseTemperature = true;
	Flashlight->Temperature = 4300.f;
	Flashlight->SetVisibility(false);

	Interaction = CreateDefaultSubobject<UVGInteractionComponent>(TEXT("Interaction"));

	bUseControllerRotationPitch = false;
	bUseControllerRotationYaw = true;
	bUseControllerRotationRoll = false;

	UCharacterMovementComponent* Move = GetCharacterMovement();
	Move->MaxWalkSpeed = WalkSpeed;
	Move->MaxAcceleration = 900.f;
	Move->BrakingDecelerationWalking = 1100.f;
	Move->GroundFriction = 7.f;
	Move->MaxStepHeight = 30.f;
	Move->AirControl = 0.1f;
}

void AVGPlayerCharacter::BeginPlay()
{
	Super::BeginPlay();
	GetCharacterMovement()->MaxWalkSpeed = WalkSpeed;

	for (const FSoftObjectPath& Path : FootstepSounds)
	{
		if (USoundBase* Sound = Cast<USoundBase>(Path.TryLoad()))
		{
			LoadedFootsteps.Add(Sound);
		}
	}
	LoadedFlashlightSound = Cast<USoundBase>(FlashlightSound.TryLoad());
}

void AVGPlayerCharacter::BuildInput()
{
	if (MappingContext)
	{
		return;
	}

	auto MakeAction = [this](const TCHAR* Name, EInputActionValueType Type)
	{
		UInputAction* Action = NewObject<UInputAction>(this, Name);
		Action->ValueType = Type;
		return Action;
	};

	MoveForwardAction = MakeAction(TEXT("IA_MoveForward"), EInputActionValueType::Axis1D);
	MoveRightAction = MakeAction(TEXT("IA_MoveRight"), EInputActionValueType::Axis1D);
	LookAction = MakeAction(TEXT("IA_Look"), EInputActionValueType::Axis2D);
	InteractAction = MakeAction(TEXT("IA_Interact"), EInputActionValueType::Boolean);
	CancelAction = MakeAction(TEXT("IA_Cancel"), EInputActionValueType::Boolean);
	RunAction = MakeAction(TEXT("IA_Run"), EInputActionValueType::Boolean);
	FlashlightAction = MakeAction(TEXT("IA_Flashlight"), EInputActionValueType::Boolean);

	MappingContext = NewObject<UInputMappingContext>(this, TEXT("IMC_Default"));

	auto MapNegated = [this](UInputAction* Action, FKey Key)
	{
		FEnhancedActionKeyMapping& Mapping = MappingContext->MapKey(Action, Key);
		Mapping.Modifiers.Add(NewObject<UInputModifierNegate>(MappingContext));
	};

	MappingContext->MapKey(MoveForwardAction, EKeys::W);
	MapNegated(MoveForwardAction, EKeys::S);
	MappingContext->MapKey(MoveForwardAction, EKeys::Up);
	MapNegated(MoveForwardAction, EKeys::Down);
	MappingContext->MapKey(MoveForwardAction, EKeys::Gamepad_LeftY);

	MappingContext->MapKey(MoveRightAction, EKeys::D);
	MapNegated(MoveRightAction, EKeys::A);
	MappingContext->MapKey(MoveRightAction, EKeys::Gamepad_LeftX);

	MappingContext->MapKey(LookAction, EKeys::Mouse2D);

	MappingContext->MapKey(InteractAction, EKeys::E);
	MappingContext->MapKey(InteractAction, EKeys::LeftMouseButton);
	MappingContext->MapKey(InteractAction, EKeys::Gamepad_FaceButton_Bottom);

	MappingContext->MapKey(CancelAction, EKeys::RightMouseButton);
	MappingContext->MapKey(CancelAction, EKeys::Q);
	MappingContext->MapKey(CancelAction, EKeys::Gamepad_FaceButton_Right);

	MappingContext->MapKey(RunAction, EKeys::LeftShift);
	MappingContext->MapKey(RunAction, EKeys::Gamepad_LeftThumbstick);

	MappingContext->MapKey(FlashlightAction, EKeys::F);
	MappingContext->MapKey(FlashlightAction, EKeys::Gamepad_FaceButton_Top);
}

void AVGPlayerCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);
	BuildInput();

	if (const APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		if (const ULocalPlayer* LocalPlayer = PC->GetLocalPlayer())
		{
			if (UEnhancedInputLocalPlayerSubsystem* Subsystem = LocalPlayer->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>())
			{
				Subsystem->RemoveMappingContext(MappingContext);
				Subsystem->AddMappingContext(MappingContext, 0);
			}
		}
	}

	UEnhancedInputComponent* Input = Cast<UEnhancedInputComponent>(PlayerInputComponent);
	if (!ensureMsgf(Input, TEXT("Vigilia necesita EnhancedInputComponent (ver Config/DefaultInput.ini)")))
	{
		return;
	}

	Input->BindAction(MoveForwardAction, ETriggerEvent::Triggered, this, &AVGPlayerCharacter::OnMoveForward);
	Input->BindAction(MoveRightAction, ETriggerEvent::Triggered, this, &AVGPlayerCharacter::OnMoveRight);
	Input->BindAction(LookAction, ETriggerEvent::Triggered, this, &AVGPlayerCharacter::OnLook);
	Input->BindAction(InteractAction, ETriggerEvent::Started, this, &AVGPlayerCharacter::OnInteract);
	Input->BindAction(CancelAction, ETriggerEvent::Started, this, &AVGPlayerCharacter::OnCancel);
	Input->BindAction(RunAction, ETriggerEvent::Started, this, &AVGPlayerCharacter::OnRunStarted);
	Input->BindAction(RunAction, ETriggerEvent::Completed, this, &AVGPlayerCharacter::OnRunCompleted);
	Input->BindAction(FlashlightAction, ETriggerEvent::Started, this, &AVGPlayerCharacter::OnFlashlight);
}

void AVGPlayerCharacter::OnMoveForward(const FInputActionValue& Value)
{
	if (!ExaminedItem)
	{
		AddMovementInput(GetActorForwardVector(), Value.Get<float>());
	}
}

void AVGPlayerCharacter::OnMoveRight(const FInputActionValue& Value)
{
	if (!ExaminedItem)
	{
		AddMovementInput(GetActorRightVector(), Value.Get<float>());
	}
}

void AVGPlayerCharacter::OnLook(const FInputActionValue& Value)
{
	const FVector2D Axis = Value.Get<FVector2D>();

	if (ExaminedItem)
	{
		// Mientras se examina, el raton gira el objeto en lugar de la camara.
		const FRotator View = GetControlRotation();
		const FVector Up = FRotationMatrix(View).GetUnitAxis(EAxis::Z);
		const FVector Right = FRotationMatrix(View).GetUnitAxis(EAxis::Y);
		const float Speed = 0.012f * MouseSensitivity;
		const FQuat DeltaYaw(Up, -Axis.X * Speed);
		const FQuat DeltaPitch(Right, -Axis.Y * Speed);
		ExamineRotation = (DeltaYaw * DeltaPitch * ExamineRotation).GetNormalized();
		return;
	}

	// Se escribe la rotacion de control directamente para no depender de las escalas
	// heredadas de entrada (InputYawScale/InputPitchScale). Mouse2D da Y positiva hacia arriba.
	if (AController* PC = GetController())
	{
		const float Scale = 0.14f * MouseSensitivity;
		FRotator Rot = PC->GetControlRotation();
		Rot.Yaw += Axis.X * Scale;
		const float Pitch = FRotator::NormalizeAxis(Rot.Pitch) + Axis.Y * Scale * (bInvertLookY ? -1.f : 1.f);
		Rot.Pitch = FMath::Clamp(Pitch, -85.f, 85.f);
		Rot.Roll = 0.f;
		PC->SetControlRotation(Rot);
	}
}

void AVGPlayerCharacter::OnInteract(const FInputActionValue& Value)
{
	if (ExaminedItem)
	{
		EndExamine();
		return;
	}
	Interaction->TryInteract();
}

void AVGPlayerCharacter::OnCancel(const FInputActionValue& Value)
{
	if (ExaminedItem)
	{
		EndExamine();
	}
}

void AVGPlayerCharacter::OnRunStarted(const FInputActionValue& Value)
{
	GetCharacterMovement()->MaxWalkSpeed = RunSpeed;
}

void AVGPlayerCharacter::OnRunCompleted(const FInputActionValue& Value)
{
	GetCharacterMovement()->MaxWalkSpeed = WalkSpeed;
}

void AVGPlayerCharacter::OnFlashlight(const FInputActionValue& Value)
{
	Flashlight->ToggleVisibility();
	if (LoadedFlashlightSound)
	{
		UGameplayStatics::PlaySound2D(this, LoadedFlashlightSound, 0.6f);
	}
}

void AVGPlayerCharacter::BeginExamine(AVGExaminable* Item)
{
	if (!Item || ExaminedItem)
	{
		return;
	}
	ExaminedItem = Item;
	Interaction->SetInteractionEnabled(false);
	GetCharacterMovement()->StopMovementImmediately();

	FVector Origin, Extent;
	Item->GetActorBounds(false, Origin, Extent, true);
	ExamineCenterLocal = Item->GetActorTransform().InverseTransformPosition(Origin);
	ExamineRotation = Item->GetActorQuat();
	ExamineDistance = FMath::Clamp(Item->GetExamineRadius() * 2.4f + 12.f, 28.f, 95.f);
	Item->BeginExamine();
}

void AVGPlayerCharacter::EndExamine()
{
	if (!ExaminedItem)
	{
		return;
	}
	ExaminedItem->EndExamine();
	ExaminedItem = nullptr;
	Interaction->SetInteractionEnabled(true);
}

void AVGPlayerCharacter::UpdateExamine()
{
	if (!ExaminedItem)
	{
		return;
	}
	const FVector Target = Camera->GetComponentLocation() + Camera->GetForwardVector() * ExamineDistance;
	const FVector Scale = ExaminedItem->GetActorScale3D();
	const FVector Location = Target - ExamineRotation.RotateVector(ExamineCenterLocal * Scale);
	ExaminedItem->SetActorLocationAndRotation(Location, ExamineRotation);
}

void AVGPlayerCharacter::UpdateFootsteps(float DeltaSeconds)
{
	const UCharacterMovementComponent* Move = GetCharacterMovement();
	const float Speed = GetVelocity().Size2D();
	if (!Move->IsMovingOnGround() || Speed < 20.f || LoadedFootsteps.Num() == 0)
	{
		StepAccumulator = FMath::Min(StepAccumulator, StepDistance * 0.6f);
		return;
	}

	StepAccumulator += Speed * DeltaSeconds;
	const bool bRunning = Speed > WalkSpeed * 1.25f;
	const float Stride = bRunning ? StepDistance * 1.45f : StepDistance;
	if (StepAccumulator >= Stride)
	{
		StepAccumulator = 0.f;
		int32 Index = FMath::RandRange(0, LoadedFootsteps.Num() - 1);
		if (LoadedFootsteps.Num() > 1 && Index == LastStepIndex)
		{
			Index = (Index + 1) % LoadedFootsteps.Num();
		}
		LastStepIndex = Index;
		const FVector Feet = GetActorLocation() - FVector(0.f, 0.f, GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
		UVGStatics::PlaySpatialSound(this, LoadedFootsteps[Index], Feet,
			bRunning ? 0.75f : 0.45f, FMath::FRandRange(0.92f, 1.08f));
	}
}

void AVGPlayerCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	UpdateExamine();
	UpdateFootsteps(DeltaSeconds);
}

void AVGPlayerCharacter::VGSetSensitivity(float NewSensitivity)
{
	MouseSensitivity = FMath::Clamp(NewSensitivity, 0.05f, 10.f);
	SaveConfig();
}

void AVGPlayerCharacter::VGInvertY(bool bInvert)
{
	bInvertLookY = bInvert;
	SaveConfig();
}

void AVGPlayerCharacter::VGQuality(int32 Level)
{
	if (UGameUserSettings* Settings = UGameUserSettings::GetGameUserSettings())
	{
		Settings->SetOverallScalabilityLevel(FMath::Clamp(Level, 0, 3));
		Settings->ApplySettings(false);
	}
}
