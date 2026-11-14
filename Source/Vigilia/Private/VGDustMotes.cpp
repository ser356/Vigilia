#include "VGDustMotes.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"

AVGDustMotes::AVGDustMotes()
{
	PrimaryActorTick.bCanEverTick = true;

	Motes = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Motes"));
	SetRootComponent(Motes);
	Motes->SetMobility(EComponentMobility::Movable);
	Motes->SetCollisionProfileName(TEXT("NoCollision"));
	Motes->SetGenerateOverlapEvents(false);
	Motes->SetCastShadow(false);
	Motes->bAffectDistanceFieldLighting = false;
	Motes->bAffectDynamicIndirectLighting = false;
}

void AVGDustMotes::SetupDust(UStaticMesh* InMesh, UMaterialInterface* InMaterial, int32 InCount, FVector InBoxExtent, float InMoteSize)
{
	Modify();
	Motes->Modify();
	Motes->SetStaticMesh(InMesh);
	if (InMaterial)
	{
		Motes->SetMaterial(0, InMaterial);
	}
	Count = InCount;
	BoxExtent = InBoxExtent;
	MoteSize = InMoteSize;
}

void AVGDustMotes::BeginPlay()
{
	Super::BeginPlay();

	if (const UStaticMesh* MeshAsset = Motes->GetStaticMesh())
	{
		MeshRadius = FMath::Max(static_cast<float>(MeshAsset->GetBounds().SphereRadius), 1.f);
	}
	Motes->ClearInstances();
	Data.Reset(Count);
	FRandomStream Rng(1994);
	for (int32 Index = 0; Index < Count; ++Index)
	{
		FMote Mote;
		Mote.Offset = FVector(Rng.FRandRange(-BoxExtent.X, BoxExtent.X), Rng.FRandRange(-BoxExtent.Y, BoxExtent.Y), Rng.FRandRange(-BoxExtent.Z, BoxExtent.Z));
		Mote.Velocity = FVector(Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-0.6f, 0.25f)) * DriftSpeed;
		Mote.Scale = Rng.FRandRange(0.5f, 1.6f);
		Mote.Phase = Rng.FRandRange(0.f, 6.28f);
		Data.Add(Mote);
		Motes->AddInstance(FTransform(Mote.Offset), false);
	}
}

void AVGDustMotes::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	const APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
	if (!PC || Data.Num() == 0)
	{
		return;
	}
	FVector ViewLocation;
	FRotator ViewRotation;
	PC->GetPlayerViewPoint(ViewLocation, ViewRotation);

	const float Time = GetWorld()->GetTimeSeconds();
	const float BaseScale = (MoteSize * 0.5f) / MeshRadius;
	const FVector Size = BoxExtent * 2.0;
	for (int32 Index = 0; Index < Data.Num(); ++Index)
	{
		FMote& Mote = Data[Index];
		// Deriva lenta con un vaiven propio de cada mota.
		const FVector Sway(FMath::Sin(Time * 0.31f + Mote.Phase), FMath::Cos(Time * 0.27f + Mote.Phase * 1.7f), FMath::Sin(Time * 0.19f + Mote.Phase * 0.6f) * 0.5f);
		Mote.Offset += (Mote.Velocity + Sway * DriftSpeed * 0.6f) * DeltaSeconds;

		// La caja sigue a la camara: lo que sale por un lado entra por el contrario.
		FVector World = Mote.Offset;
		FVector Rel = World - ViewLocation;
		Rel.X = FMath::Fmod(Rel.X + BoxExtent.X, Size.X); if (Rel.X < 0.0) { Rel.X += Size.X; } Rel.X -= BoxExtent.X;
		Rel.Y = FMath::Fmod(Rel.Y + BoxExtent.Y, Size.Y); if (Rel.Y < 0.0) { Rel.Y += Size.Y; } Rel.Y -= BoxExtent.Y;
		Rel.Z = FMath::Fmod(Rel.Z + BoxExtent.Z, Size.Z); if (Rel.Z < 0.0) { Rel.Z += Size.Z; } Rel.Z -= BoxExtent.Z;
		Mote.Offset = ViewLocation + Rel;

		const FTransform Xf(FQuat::Identity, Mote.Offset, FVector(BaseScale * Mote.Scale));
		Motes->UpdateInstanceTransform(Index, Xf, true, Index == Data.Num() - 1, true);
	}
}
