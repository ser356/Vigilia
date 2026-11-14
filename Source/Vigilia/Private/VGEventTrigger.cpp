#include "VGEventTrigger.h"
#include "VGLamp.h"
#include "VGTelevision.h"
#include "VGDoor.h"
#include "VGStatics.h"
#include "VGPhone.h"
#include "VGPlayerCharacter.h"
#include "VGLoopSubsystem.h"
#include "Components/AudioComponent.h"
#include "Components/BoxComponent.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"
#include "TimerManager.h"
#include "Engine/World.h"

AVGEventTrigger::AVGEventTrigger()
{
	Box = CreateDefaultSubobject<UBoxComponent>(TEXT("Box"));
	SetRootComponent(Box);
	Box->SetBoxExtent(FVector(60.f, 60.f, 100.f));
	Box->SetCollisionProfileName(TEXT("Trigger"));
	Box->SetGenerateOverlapEvents(true);
}

void AVGEventTrigger::BeginPlay()
{
	Super::BeginPlay();
	Box->OnComponentBeginOverlap.AddDynamic(this, &AVGEventTrigger::HandleOverlap);
	if (RequiredLoop >= 0)
	{
		if (UVGLoopSubsystem* Loop = GetWorld()->GetSubsystem<UVGLoopSubsystem>())
		{
			Loop->OnLoopAdvanced.AddDynamic(this, &AVGEventTrigger::HandleLoop);
		}
	}
	if (AutoFireAfter >= 0.f)
	{
		FTimerHandle Handle;
		GetWorldTimerManager().SetTimer(Handle, this, &AVGEventTrigger::TryAutoFire, FMath::Max(AutoFireAfter, 0.1f), false);
	}
}

void AVGEventTrigger::HandleLoop(int32 LoopCount)
{
	if (LoopCount == RequiredLoop && !(bOnce && bFired))
	{
		Fire();
	}
}

void AVGEventTrigger::AddMessageStep(float Delay, const FText& Text, float Duration)
{
	Modify();
	FVGEventStep& Step = Steps.AddDefaulted_GetRef();
	Step.Action = EVGEventAction::ShowMessage;
	Step.Delay = Delay;
	Step.Message = Text;
	Step.Offset = FTransform(FVector(Duration, 0.f, 0.f));
}

bool AVGEventTrigger::IsPlayerInside() const
{
	const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0);
	if (!Pawn)
	{
		return false;
	}
	const FVector Local = Box->GetComponentTransform().InverseTransformPosition(Pawn->GetActorLocation());
	const FVector Extent = Box->GetUnscaledBoxExtent();
	return FMath::Abs(Local.X) <= Extent.X && FMath::Abs(Local.Y) <= Extent.Y && FMath::Abs(Local.Z) <= Extent.Z + 100.f;
}

void AVGEventTrigger::TryAutoFire()
{
	if (bOnce && bFired)
	{
		return;
	}
	if (bRequirePlayerInside && !IsPlayerInside())
	{
		FTimerHandle Handle;
		GetWorldTimerManager().SetTimer(Handle, this, &AVGEventTrigger::TryAutoFire, 4.f, false);
		return;
	}
	Fire();
}

void AVGEventTrigger::AddStep(EVGEventAction Action, AActor* Target, float Delay, USoundBase* Sound, FTransform Offset, bool bOnlyWhenUnseen)
{
	Modify();
	FVGEventStep& Step = Steps.AddDefaulted_GetRef();
	Step.Action = Action;
	Step.Target = Target;
	Step.Delay = Delay;
	Step.Sound = Sound;
	Step.Offset = Offset;
	Step.bOnlyWhenUnseen = bOnlyWhenUnseen;
}

void AVGEventTrigger::SetBoxExtent(FVector Extent)
{
	Box->Modify();
	Box->SetBoxExtent(Extent);
}

void AVGEventTrigger::HandleOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult)
{
	const APawn* Pawn = Cast<APawn>(OtherActor);
	if (!bFireOnOverlap || !Pawn || !Pawn->IsPlayerControlled())
	{
		return;
	}
	++Entries;
	if ((bOnce && bFired) || Entries < RequiredEntries)
	{
		return;
	}
	if (GetWorld()->GetTimeSeconds() < MinGameTime || FMath::FRand() > Chance)
	{
		return;
	}
	Fire();
}

void AVGEventTrigger::Fire()
{
	bFired = true;
	OnTriggered.Broadcast(this);
	if (RepeatInterval > 0.f)
	{
		FTimerHandle Repeat;
		GetWorldTimerManager().SetTimer(Repeat, this, &AVGEventTrigger::Fire, RepeatInterval, false);
	}

	for (int32 Index = 0; Index < Steps.Num(); ++Index)
	{
		if (Steps[Index].Delay <= 0.f)
		{
			ExecuteStep(Index);
		}
		else
		{
			FTimerHandle Handle;
			GetWorldTimerManager().SetTimer(Handle, FTimerDelegate::CreateUObject(this, &AVGEventTrigger::ExecuteStep, Index), Steps[Index].Delay, false);
		}
	}
}

void AVGEventTrigger::ExecuteStepWhenUnseen(int32 Index, int32 Attempt)
{
	if (!Steps.IsValidIndex(Index) || Attempt > 160)
	{
		return;
	}
	if (IsSeenByPlayer(Steps[Index].Target))
	{
		FTimerHandle Retry;
		GetWorldTimerManager().SetTimer(Retry, FTimerDelegate::CreateUObject(this, &AVGEventTrigger::ExecuteStepWhenUnseen, Index, Attempt + 1), 0.25f, false);
		return;
	}
	FVGEventStep Copy = Steps[Index];
	Copy.bOnlyWhenUnseen = false;
	Steps.Add(Copy);
	ExecuteStep(Steps.Num() - 1);
	Steps.Pop();
}

bool AVGEventTrigger::IsSeenByPlayer(const AActor* Target) const
{
	const APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
	if (!PC || !Target)
	{
		return false;
	}
	FVector ViewLocation;
	FRotator ViewRotation;
	PC->GetPlayerViewPoint(ViewLocation, ViewRotation);
	const FVector ToTarget = (Target->GetActorLocation() - ViewLocation).GetSafeNormal();
	// Margen amplio: cubre el campo de vision completo mas la vision periferica.
	return FVector::DotProduct(ViewRotation.Vector(), ToTarget) > 0.25f;
}

void AVGEventTrigger::ExecuteStep(int32 Index)
{
	if (!Steps.IsValidIndex(Index))
	{
		return;
	}
	const FVGEventStep& Step = Steps[Index];
	AActor* Target = Step.Target;

	if (Step.bOnlyWhenUnseen && IsSeenByPlayer(Target))
	{
		// No se descarta: espera a que el jugador aparte la vista.
		ExecuteStepWhenUnseen(Index, 1);
		return;
	}

	switch (Step.Action)
	{
	case EVGEventAction::LampOn:
	case EVGEventAction::LampOff:
		if (AVGLamp* Lamp = Cast<AVGLamp>(Target))
		{
			Lamp->SetOn(Step.Action == EVGEventAction::LampOn, true);
		}
		break;
	case EVGEventAction::LampFlicker:
		if (AVGLamp* Lamp = Cast<AVGLamp>(Target))
		{
			// La escala X del Offset actua como multiplicador de duracion (1 = 1,6 s).
			const float Duration = static_cast<float>(Step.Offset.GetScale3D().X) * 1.6f;
			Lamp->Flicker(FMath::Max(Duration, 0.3f), Lamp->IsOn());
		}
		break;
	case EVGEventAction::TVOn:
	case EVGEventAction::TVOff:
		if (AVGTelevision* TV = Cast<AVGTelevision>(Target))
		{
			TV->SetOn(Step.Action == EVGEventAction::TVOn, true);
		}
		break;
	case EVGEventAction::DoorOpen:
		if (AVGDoor* Door = Cast<AVGDoor>(Target))
		{
			// Las puertas que se abren solas lo hacen despacio y solo un poco.
			const float Saved = Door->OpenAngle;
			Door->OpenAngle = 22.f;
			Door->OpenDoor(Door->PreferredOpenSign != 0.f ? Door->PreferredOpenSign : 1.f, 3.2f);
			Door->OpenAngle = Saved;
		}
		break;
	case EVGEventAction::DoorClose:
	case EVGEventAction::DoorSlam:
		if (AVGDoor* Door = Cast<AVGDoor>(Target))
		{
			Door->CloseDoor(Step.Action == EVGEventAction::DoorSlam);
		}
		break;
	case EVGEventAction::PlaySound:
		if (Step.Sound)
		{
			const FVector Location = (Target ? Target->GetActorLocation() : GetActorLocation()) + Step.Offset.GetLocation();
			UVGStatics::PlaySpatialSound(this, Step.Sound, Location);
		}
		break;
	case EVGEventAction::MoveActor:
		if (Target)
		{
			Target->AddActorWorldOffset(Step.Offset.GetLocation());
			Target->AddActorWorldRotation(Step.Offset.GetRotation());
		}
		break;
	case EVGEventAction::ToggleVisibility:
		if (Target)
		{
			Target->SetActorHiddenInGame(!Target->IsHidden());
		}
		break;
	case EVGEventAction::AudioPlay:
	case EVGEventAction::AudioStop:
		if (Target)
		{
			if (UAudioComponent* AudioComp = Target->FindComponentByClass<UAudioComponent>())
			{
				if (Step.Action == EVGEventAction::AudioPlay)
				{
					AudioComp->FadeIn(0.3f);
				}
				else
				{
					AudioComp->FadeOut(0.15f, 0.f);
				}
			}
		}
		break;
	case EVGEventAction::SoundBehindPlayer:
		if (Step.Sound)
		{
			if (const APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
			{
				FVector ViewLocation;
				FRotator ViewRotation;
				PC->GetPlayerViewPoint(ViewLocation, ViewRotation);
				const float Distance = Step.Offset.GetLocation().X > 1.f ? static_cast<float>(Step.Offset.GetLocation().X) : 70.f;
				const FVector Behind = ViewLocation - FRotator(0.f, ViewRotation.Yaw, 0.f).Vector() * Distance + FVector(0.f, 0.f, 8.f);
				UVGStatics::PlaySpatialSound(this, Step.Sound, Behind, 0.9f, 1.f);
			}
		}
		break;
	case EVGEventAction::PhoneRing:
		if (AVGPhone* Phone = Cast<AVGPhone>(Target))
		{
			Phone->Ring();
		}
		break;
	case EVGEventAction::FacePlayer:
		if (Target)
		{
			if (const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0))
			{
				const FVector To = Pawn->GetActorLocation() - Target->GetActorLocation();
				const float Yaw = FMath::RadiansToDegrees(FMath::Atan2(To.Y, To.X)) + static_cast<float>(Step.Offset.Rotator().Yaw);
				FRotator Rot = Target->GetActorRotation();
				Rot.Yaw = Yaw;
				Target->SetActorRotation(Rot);
			}
		}
		break;
	case EVGEventAction::FlashlightFail:
		if (AVGPlayerCharacter* Player = Cast<AVGPlayerCharacter>(UGameplayStatics::GetPlayerPawn(this, 0)))
		{
			const float Duration = Step.Offset.GetLocation().X > 0.1 ? static_cast<float>(Step.Offset.GetLocation().X) : 3.f;
			Player->FailFlashlight(Duration);
		}
		break;
	case EVGEventAction::DoorLock:
	case EVGEventAction::DoorUnlock:
		if (AVGDoor* Door = Cast<AVGDoor>(Target))
		{
			Door->SetLocked(Step.Action == EVGEventAction::DoorLock);
		}
		break;
	case EVGEventAction::LampColor:
		if (AVGLamp* Lamp = Cast<AVGLamp>(Target))
		{
			const FVector C = Step.Offset.GetScale3D();
			Lamp->SetColor(FLinearColor(static_cast<float>(C.X), static_cast<float>(C.Y), static_cast<float>(C.Z)));
		}
		break;
	case EVGEventAction::ShowMessage:
		if (UVGLoopSubsystem* Loop = GetWorld()->GetSubsystem<UVGLoopSubsystem>())
		{
			const float Duration = Step.Offset.GetLocation().X > 0.1 ? static_cast<float>(Step.Offset.GetLocation().X) : 4.f;
			Loop->ShowMessage(Step.Message, Duration);
		}
		break;
	case EVGEventAction::FireTrigger:
		if (AVGEventTrigger* Other = Cast<AVGEventTrigger>(Target))
		{
			Other->Fire();
		}
		break;
	}
}
