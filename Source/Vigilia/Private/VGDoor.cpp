#include "VGDoor.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshResources.h"

AVGDoor::AVGDoor()
{
	Hinge = CreateDefaultSubobject<USceneComponent>(TEXT("Hinge"));
	Hinge->SetupAttachment(Root);
	Hinge->SetMobility(EComponentMobility::Movable);
	Mesh->SetupAttachment(Hinge);
	Prompt = NSLOCTEXT("Vigilia", "Door", "Puerta");
}

FVector AVGDoor::SetupDoorMesh(UStaticMesh* InMesh, float TargetWidth)
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
	FRotator Rot = (Size.X > Size.Y) ? FRotator(0.f, 90.f, 0.f) : FRotator::ZeroRotator;
	FBox R = Box.TransformBy(FTransform(Rot));

	// La bisagra debe quedar en el lado contrario al pomo. El pomo es lo que mas sobresale del
	// grosor de la hoja a media altura: si esta cerca de la bisagra (Y minima), se gira la malla 180.
	if (InMesh->GetRenderData() && InMesh->GetRenderData()->LODResources.Num() > 0)
	{
		const FPositionVertexBuffer& Positions = InMesh->GetRenderData()->LODResources[0].VertexBuffers.PositionVertexBuffer;
		const FTransform RotOnly(Rot);
		const double CenterX = (R.Min.X + R.Max.X) * 0.5;
		const double HalfThickness = FMath::Max((R.Max.X - R.Min.X) * 0.5, 0.1);
		const double ZLow = R.Min.Z + (R.Max.Z - R.Min.Z) * 0.3;
		const double ZHigh = R.Min.Z + (R.Max.Z - R.Min.Z) * 0.65;
		double SumY = 0.0;
		int32 Count = 0;
		for (uint32 Index = 0; Index < Positions.GetNumVertices(); ++Index)
		{
			const FVector P = RotOnly.TransformPosition(FVector(Positions.VertexPosition(Index)));
			if (P.Z >= ZLow && P.Z <= ZHigh && FMath::Abs(P.X - CenterX) > HalfThickness * 0.6)
			{
				SumY += P.Y;
				++Count;
			}
		}
		if (Count > 0)
		{
			const double KnobY = SumY / Count;
			const bool bKnobNearHinge = KnobY < (R.Min.Y + R.Max.Y) * 0.5;
			if (bKnobNearHinge != bSwapHingeSide)
			{
				Rot.Yaw += 180.f;
				R = Box.TransformBy(FTransform(Rot));
			}
		}
	}

	const FVector Offset(-(R.Min.X + R.Max.X) * 0.5f, -R.Min.Y, -R.Min.Z);
	Mesh->SetRelativeLocationAndRotation(Offset, Rot);

	// Ancho exacto de la hoja: se escala la bisagra (gira con la hoja, sin deformarla).
	Hinge->Modify();
	const double Width = FMath::Max(R.Max.Y - R.Min.Y, 1.0);
	const double ScaleY = TargetWidth > 1.f ? TargetWidth / Width : 1.0;
	Hinge->SetRelativeScale3D(FVector(1.0, ScaleY, 1.0));
	return FVector(R.Max.X - R.Min.X, Width * ScaleY, R.Max.Z - R.Min.Z);
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
	Mesh->SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore);
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
		// Cerrada: vuelve a bloquear al jugador. Abierta: no estorba nunca el paso.
		Mesh->SetCollisionResponseToChannel(ECC_Pawn, bOpen ? ECR_Ignore : ECR_Block);
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
