#include "VGEntity.h"
#include "VGLamp.h"
#include "VGStatics.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Animation/AnimationAsset.h"
#include "Components/AudioComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "Sound/SoundBase.h"
#include "Engine/StaticMesh.h"

AVGEntity::AVGEntity()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = false;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);

	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	Mesh->SetupAttachment(Root);
	Mesh->SetMobility(EComponentMobility::Movable);
	Mesh->SetCollisionProfileName(TEXT("NoCollision"));
	Mesh->SetGenerateOverlapEvents(false);

	Body = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("Body"));
	Body->SetupAttachment(Root);
	Body->SetCollisionProfileName(TEXT("NoCollision"));
	Body->SetGenerateOverlapEvents(false);
	// Se anima aunque no este en pantalla: asi no aparece "congelada" al entrar en el encuadre.
	Body->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;

	Audio = CreateDefaultSubobject<UAudioComponent>(TEXT("Audio"));
	Audio->SetupAttachment(Root);
	Audio->SetRelativeLocation(FVector(0.f, 0.f, 150.f));
	Audio->bAutoActivate = false;
	Audio->bOverrideAttenuation = true;
	Audio->AttenuationOverrides.bSpatialize = true;
	Audio->AttenuationOverrides.bAttenuate = true;
	Audio->AttenuationOverrides.FalloffDistance = 1800.f;
	Audio->AttenuationOverrides.AttenuationShapeExtents = FVector(150.f);
}

void AVGEntity::SetupEntity(UStaticMesh* InMesh, UMaterialInterface* SilhouetteMaterial, FVector RelativeLocation, float InMeshYawOffset, float UniformScale)
{
	Modify();
	Mesh->Modify();
	Mesh->SetStaticMesh(InMesh);
	Mesh->SetRelativeLocation(RelativeLocation);
	Mesh->SetRelativeScale3D(FVector(UniformScale));
	MeshYawOffset = InMeshYawOffset;
	if (InMesh && SilhouetteMaterial)
	{
		const int32 Slots = InMesh->GetStaticMaterials().Num();
		for (int32 Index = 0; Index < Slots; ++Index)
		{
			Mesh->SetMaterial(Index, SilhouetteMaterial);
		}
	}
}

void AVGEntity::SetupSkeletal(USkeletalMesh* InMesh, UAnimationAsset* InIdle, UAnimationAsset* InWalk, UAnimationAsset* InRun, UMaterialInterface* SilhouetteMaterial, FVector RelativeLocation, float InMeshYawOffset, float UniformScale)
{
	Modify();
	Body->Modify();
	Body->SetSkeletalMesh(InMesh);
	Body->SetRelativeLocation(RelativeLocation);
	Body->SetRelativeScale3D(FVector(UniformScale));
	IdleAnim = InIdle;
	WalkAnim = InWalk;
	RunAnim = InRun;
	MeshYawOffset = InMeshYawOffset;
	if (InMesh && SilhouetteMaterial)
	{
		const int32 Slots = InMesh->GetMaterials().Num();
		for (int32 Index = 0; Index < Slots; ++Index)
		{
			Body->SetMaterial(Index, SilhouetteMaterial);
		}
	}
}

bool AVGEntity::HasBody() const
{
	return Body && Body->GetSkeletalMeshAsset() != nullptr;
}

void AVGEntity::AddStepSound(USoundBase* Sound)
{
	if (Sound)
	{
		Modify();
		StepSounds.AddUnique(Sound);
	}
}

void AVGEntity::PlayAnim(UAnimationAsset* Anim, float Rate)
{
	if (!HasBody() || !Anim)
	{
		return;
	}
	Body->SetAnimationMode(EAnimationMode::AnimationSingleNode);
	Body->PlayAnimation(Anim, true);
	Body->SetPlayRate(Rate);
}

void AVGEntity::PlayMoveAnim(float Speed)
{
	// Sin animacion de correr se usa la de andar acelerada (y al reves).
	if (Speed > 260.f && RunAnim)
	{
		PlayAnim(RunAnim, FMath::Clamp(Speed / RunAnimSpeed, 0.7f, 1.8f));
	}
	else if (WalkAnim)
	{
		PlayAnim(WalkAnim, FMath::Clamp(Speed / WalkAnimSpeed, 0.7f, 3.2f));
	}
	else if (RunAnim)
	{
		PlayAnim(RunAnim, FMath::Clamp(Speed / RunAnimSpeed, 0.4f, 1.8f));
	}
}

void AVGEntity::FaceDirection(const FVector& Direction)
{
	const float Yaw = FMath::RadiansToDegrees(FMath::Atan2(Direction.Y, Direction.X)) + MeshYawOffset;
	SetActorRotation(FRotator(0.f, Yaw, 0.f));
}

void AVGEntity::Footsteps(float MovedDistance)
{
	if (StepSounds.Num() == 0)
	{
		return;
	}
	StepAccumulator += MovedDistance;
	if (StepAccumulator >= 85.f)
	{
		StepAccumulator = 0.f;
		USoundBase* Sound = StepSounds[FMath::RandRange(0, StepSounds.Num() - 1)];
		UVGStatics::PlaySpatialSound(this, Sound, GetActorLocation(), 1.f, FMath::FRandRange(0.9f, 1.05f));
	}
}

void AVGEntity::RunTo(FVector From, FVector To, float Speed)
{
	SetActorLocation(From);
	RunTarget = To;
	RunSpeed = FMath::Max(Speed, 50.f);
	FaceDirection(To - From);
	SetActorHiddenInGame(false);
	State = EVGEntityState::Running;
	TimeLeft = 30.f;
	StepAccumulator = 60.f;
	SetActorTickEnabled(true);
	PlayMoveAnim(RunSpeed);
}

void AVGEntity::AddLinkedLamp(AVGLamp* Lamp)
{
	if (Lamp)
	{
		Modify();
		LinkedLamps.AddUnique(Lamp);
	}
}

void AVGEntity::BeginPlay()
{
	Super::BeginPlay();
	SetActorHiddenInGame(true);
	State = EVGEntityState::Hidden;
}

APawn* AVGEntity::GetPlayer() const
{
	return UGameplayStatics::GetPlayerPawn(this, 0);
}

void AVGEntity::FacePlayer()
{
	if (const APawn* Player = GetPlayer())
	{
		const FVector To = Player->GetActorLocation() - GetActorLocation();
		const float Yaw = FMath::RadiansToDegrees(FMath::Atan2(To.Y, To.X)) + MeshYawOffset;
		SetActorRotation(FRotator(0.f, Yaw, 0.f));
	}
}

void AVGEntity::FlickerLamps(float Duration)
{
	for (AVGLamp* Lamp : LinkedLamps)
	{
		if (Lamp && Lamp->IsOn())
		{
			Lamp->Flicker(Duration, true);
		}
	}
}

void AVGEntity::Appear(FVector Location)
{
	SetActorLocation(Location);
	FacePlayer();
	SetActorHiddenInGame(false);
	State = EVGEntityState::Watching;
	WatchVanishDistance = 0.f;
	TimeLeft = 3600.f;
	SetActorTickEnabled(true);
	PlayAnim(IdleAnim, 1.f);
	FlickerLamps(0.6f);
	if (AppearSound)
	{
		Audio->SetSound(AppearSound);
		Audio->SetVolumeMultiplier(0.8f);
		Audio->Play();
	}
}

void AVGEntity::Watch(float VanishDistance, float MaxSeconds)
{
	if (State == EVGEntityState::Hidden)
	{
		return;
	}
	State = EVGEntityState::Watching;
	WatchVanishDistance = VanishDistance;
	TimeLeft = FMath::Max(MaxSeconds, 0.5f);
}

void AVGEntity::Chase(float Speed, float MaxSeconds)
{
	if (State == EVGEntityState::Hidden)
	{
		return;
	}
	State = EVGEntityState::Chasing;
	ChaseSpeed = Speed;
	TimeLeft = FMath::Max(MaxSeconds, 0.5f);
	StepTimer = 0.f;
	PendingAdvance = 0.f;
	StepAccumulator = 60.f;
	PlayMoveAnim(ChaseSpeed);
	if (ChaseLoopSound)
	{
		Audio->SetSound(ChaseLoopSound);
		Audio->SetVolumeMultiplier(1.f);
		Audio->Play();
	}
}

void AVGEntity::Vanish(bool bWithSound)
{
	if (State == EVGEntityState::Hidden)
	{
		return;
	}
	State = EVGEntityState::Hidden;
	SetActorHiddenInGame(true);
	SetActorTickEnabled(false);
	Audio->Stop();
	FlickerLamps(0.5f);
	if (bWithSound && CatchSound)
	{
		UVGStatics::PlaySpatialSound(this, CatchSound, GetActorLocation() + FVector(0.f, 0.f, 150.f), 1.f, 1.f);
	}
}

void AVGEntity::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	APawn* Player = GetPlayer();
	if (!Player || State == EVGEntityState::Hidden)
	{
		return;
	}

	TimeLeft -= DeltaSeconds;
	FVector To = Player->GetActorLocation() - GetActorLocation();
	To.Z = 0.f;
	const float Distance = static_cast<float>(To.Size());

	if (State == EVGEntityState::Running)
	{
		FVector Delta = RunTarget - GetActorLocation();
		Delta.Z = 0.f;
		const float Remaining = static_cast<float>(Delta.Size());
		const float Move = RunSpeed * DeltaSeconds;
		if (Remaining <= Move || TimeLeft <= 0.f)
		{
			// Al llegar se esfuma sin mas: quien mira solo ve que "ya no esta".
			State = EVGEntityState::Hidden;
			SetActorHiddenInGame(true);
			SetActorTickEnabled(false);
			return;
		}
		AddActorWorldOffset(Delta / Remaining * Move);
		Footsteps(Move);
		return;
	}

	if (State == EVGEntityState::Watching)
	{
		FacePlayer();
		if (TimeLeft <= 0.f || (WatchVanishDistance > 0.f && Distance < WatchVanishDistance))
		{
			Vanish(false);
		}
		return;
	}

	if (HasBody())
	{
		// Cuerpo animado: carrera continua hacia el jugador.
		if (Distance > CatchDistance * 0.5f)
		{
			const float Move = FMath::Min(ChaseSpeed * DeltaSeconds, Distance - CatchDistance * 0.5f);
			AddActorWorldOffset(To / Distance * Move);
			Footsteps(Move);
		}
		FacePlayer();
		PendingAdvance = 0.f;
		StepTimer = 1.f;
	}

	// Silueta estatica: acumula avance y lo aplica a tirones, como fotogramas que faltan.
	PendingAdvance += HasBody() ? 0.f : ChaseSpeed * DeltaSeconds;
	StepTimer -= DeltaSeconds;
	if (StepTimer <= 0.f)
	{
		StepTimer = StepInterval * FMath::FRandRange(0.7f, 1.4f);
		const float Advance = FMath::Min(PendingAdvance, FMath::Max(Distance - CatchDistance * 0.5f, 0.f));
		PendingAdvance = 0.f;
		if (Distance > 1.f)
		{
			AddActorWorldOffset(To / Distance * Advance);
		}
		FacePlayer();
	}

	if (Distance <= CatchDistance)
	{
		if (APlayerController* PC = Cast<APlayerController>(Player->GetController()))
		{
			if (PC->PlayerCameraManager)
			{
				PC->PlayerCameraManager->StartCameraFade(1.f, 0.f, 2.2f, FLinearColor::Black, false, false);
			}
		}
		if (CatchSound)
		{
			UGameplayStatics::PlaySound2D(this, CatchSound, 1.f);
		}
		Vanish(false);
	}
	else if (TimeLeft <= 0.f)
	{
		Vanish(false);
	}
}
