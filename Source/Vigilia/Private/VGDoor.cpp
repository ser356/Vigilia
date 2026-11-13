#include "VGDoor.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"

AVGDoor::AVGDoor()
{
	Hinge = CreateDefaultSubobject<USceneComponent>(TEXT("Hinge"));
	Hinge->SetupAttachment(Root);
	Hinge->SetMobility(EComponentMobility::Movable);
	Mesh->SetupAttachment(Hinge);
	Prompt = NSLOCTEXT("Vigilia", "Door", "Puerta");
}

FVector AVGDoor::SetupDoorMesh(UStaticMesh* InMesh)
{
	Modify();
	Mesh->Modify();
	Mesh->SetStaticMesh(InMesh);
	if (!InMesh)
	{
		return FVector::ZeroVector;
	}

	const FBox Box = InMesh->GetBoundingBox();
	const FVector Size = Box.GetSize();
	// El ancho de la hoja es la mayor dimension horizontal; debe quedar sobre +Y.
	const FRotator Rot = (Size.X > Size.Y) ? FRotator(0.f, 90.f, 0.f) : FRotator::ZeroRotator;
	const FBox R = Box.TransformBy(FTransform(Rot));

	const FVector Offset(-(R.Min.X + R.Max.X) * 0.5f, -R.Min.Y, -R.Min.Z);
	Mesh->SetRelativeLocationAndRotation(Offset, Rot);
	return R.GetSize();
}

FText AVGDoor::GetInteractionPrompt_Implementation(AActor* Interactor) const
{
	if (bLocked)
	{
		return NSLOCTEXT("Vigilia", "DoorLocked", "Cerrada con llave");
	}
	return bOpen ? NSLOCTEXT("Vigilia", "DoorClose", "Cerrar puerta") : NSLOCTEXT("Vigilia", "DoorOpen", "Abrir puerta");
}

void AVGDoor::Interact_Implementation(AActor* Interactor)
{
	if (bLocked)
	{
		PlayLocalSound(LockedSound);
		return;
	}
	if (bOpen)
	{
		CloseDoor(false);
	}
	else
	{
		float Sign = 1.f;
		if (bOpenAwayFromInteractor && Interactor)
		{
			const FVector ToInteractor = Interactor->GetActorLocation() - GetActorLocation();
			// Yaw positivo lleva el canto libre (+Y) hacia -X: se usa cuando el jugador esta en +X.
			Sign = FVector::DotProduct(ToInteractor, GetActorForwardVector()) >= 0.f ? 1.f : -1.f;
		}
		OpenDoor(Sign);
	}
	Super::Interact_Implementation(Interactor);
}

void AVGDoor::OpenDoor(float DirectionSign, float DurationOverride)
{
	bOpen = true;
	bPendingCloseSound = false;
	bPendingSlam = false;
	PlayLocalSound(OpenSound, 1.f, FMath::FRandRange(0.94f, 1.06f));
	StartMove(OpenAngle * (DirectionSign >= 0.f ? 1.f : -1.f), DurationOverride > 0.f ? DurationOverride : OpenDuration);
}

void AVGDoor::CloseDoor(bool bSlam)
{
	if (!bOpen && MoveAlpha >= 1.f)
	{
		return;
	}
	bOpen = false;
	bPendingSlam = bSlam;
	bPendingCloseSound = !bSlam;
	if (!bSlam)
	{
		PlayLocalSound(OpenSound, 0.8f, FMath::FRandRange(0.85f, 0.95f));
	}
	StartMove(0.f, bSlam ? 0.22f : OpenDuration);
}

void AVGDoor::StartMove(float NewTargetYaw, float Duration)
{
	StartYaw = Hinge->GetRelativeRotation().Yaw;
	TargetYaw = NewTargetYaw;
	MoveDuration = FMath::Max(Duration, 0.05f);
	MoveAlpha = 0.f;
	SetActorTickEnabled(true);
}

void AVGDoor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	MoveAlpha = FMath::Min(1.f, MoveAlpha + DeltaSeconds / MoveDuration);
	const float Eased = bPendingSlam ? MoveAlpha * MoveAlpha : FMath::InterpEaseInOut(0.f, 1.f, MoveAlpha, 2.2f);
	Hinge->SetRelativeRotation(FRotator(0.f, FMath::Lerp(StartYaw, TargetYaw, Eased), 0.f));

	if (MoveAlpha >= 1.f)
	{
		SetActorTickEnabled(false);
		if (bPendingSlam)
		{
			PlayLocalSound(SlamSound ? SlamSound.Get() : CloseSound.Get(), 1.f);
		}
		else if (bPendingCloseSound)
		{
			PlayLocalSound(CloseSound, 0.9f, FMath::FRandRange(0.95f, 1.05f));
		}
		bPendingSlam = false;
		bPendingCloseSound = false;
	}
}
