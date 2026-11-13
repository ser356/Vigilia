#include "VGInteractableActor.h"
#include "Components/StaticMeshComponent.h"
#include "Components/AudioComponent.h"
#include "Sound/SoundBase.h"

AVGInteractableActor::AVGInteractableActor()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = false;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);

	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	Mesh->SetupAttachment(Root);
	Mesh->SetMobility(EComponentMobility::Movable);
	Mesh->SetCollisionProfileName(TEXT("BlockAll"));

	Audio = CreateDefaultSubobject<UAudioComponent>(TEXT("Audio"));
	Audio->SetupAttachment(Root);
	Audio->bAutoActivate = false;
	Audio->bOverrideAttenuation = true;
	Audio->AttenuationOverrides.bSpatialize = true;
	Audio->AttenuationOverrides.bAttenuate = true;
	Audio->AttenuationOverrides.FalloffDistance = 1400.f;
	Audio->AttenuationOverrides.AttenuationShapeExtents = FVector(120.f);
	// Oclusion: a traves de paredes y puertas cerradas el sonido se apaga y pierde agudos.
	Audio->AttenuationOverrides.bEnableOcclusion = true;
	Audio->AttenuationOverrides.OcclusionTraceChannel = ECC_Visibility;
	Audio->AttenuationOverrides.OcclusionLowPassFilterFrequency = 700.f;
	Audio->AttenuationOverrides.OcclusionVolumeAttenuation = 0.35f;
	Audio->AttenuationOverrides.OcclusionInterpolationTime = 0.25f;
	Audio->AttenuationOverrides.bEnableReverbSend = true;


	Prompt = NSLOCTEXT("Vigilia", "DefaultPrompt", "Usar");
}

FText AVGInteractableActor::GetInteractionPrompt_Implementation(AActor* Interactor) const
{
	return Prompt;
}

bool AVGInteractableActor::CanInteract_Implementation(AActor* Interactor) const
{
	return bInteractionEnabled;
}

void AVGInteractableActor::Interact_Implementation(AActor* Interactor)
{
	OnInteracted.Broadcast(this, Interactor);
}

void AVGInteractableActor::SetFocused_Implementation(bool bFocused)
{
}

void AVGInteractableActor::SetupMesh(UStaticMesh* InMesh, FVector RelativeLocation, FRotator RelativeRotation)
{
	Modify();
	Mesh->Modify();
	Mesh->SetStaticMesh(InMesh);
	Mesh->SetRelativeLocationAndRotation(RelativeLocation, RelativeRotation);
}

void AVGInteractableActor::PlayLocalSound(USoundBase* Sound, float Volume, float Pitch)
{
	if (!Sound || !Audio)
	{
		return;
	}
	Audio->SetSound(Sound);
	Audio->SetVolumeMultiplier(Volume);
	Audio->SetPitchMultiplier(Pitch);
	Audio->Play();
}
