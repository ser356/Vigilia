#include "VGEntity.h"
#include "VGLamp.h"
#include "VGStatics.h"
#include "Components/StaticMeshComponent.h"
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

	if (State == EVGEntityState::Watching)
	{
		FacePlayer();
		if (TimeLeft <= 0.f || (WatchVanishDistance > 0.f && Distance < WatchVanishDistance))
		{
			Vanish(false);
		}
		return;
	}

	// Persecucion: acumula avance y lo aplica a tirones, como fotogramas que faltan.
	PendingAdvance += ChaseSpeed * DeltaSeconds;
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
