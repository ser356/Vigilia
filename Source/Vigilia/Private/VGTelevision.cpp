#include "VGTelevision.h"
#include "Components/RectLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/AudioComponent.h"
#include "Materials/MaterialInstanceDynamic.h"

AVGTelevision::AVGTelevision()
{
	ScreenPlane = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ScreenPlane"));
	ScreenPlane->SetupAttachment(Root);
	ScreenPlane->SetCollisionProfileName(TEXT("NoCollision"));
	ScreenPlane->SetCastShadow(false);
	ScreenPlane->SetVisibility(false);

	ScreenGlow = CreateDefaultSubobject<URectLightComponent>(TEXT("ScreenGlow"));
	ScreenGlow->SetupAttachment(Root);
	ScreenGlow->SetMobility(EComponentMobility::Movable);
	ScreenGlow->SetIntensityUnits(ELightUnits::Lumens);
	ScreenGlow->SetIntensity(0.f);
	ScreenGlow->SetLightColor(FLinearColor(0.62f, 0.74f, 1.f));
	ScreenGlow->SetAttenuationRadius(520.f);
	ScreenGlow->BarnDoorAngle = 80.f;
	ScreenGlow->SetVisibility(false);

	LoopAudio = CreateDefaultSubobject<UAudioComponent>(TEXT("LoopAudio"));
	LoopAudio->SetupAttachment(Root);
	LoopAudio->bAutoActivate = false;
	LoopAudio->bOverrideAttenuation = true;
	LoopAudio->AttenuationOverrides.bSpatialize = true;
	LoopAudio->AttenuationOverrides.bAttenuate = true;
	LoopAudio->AttenuationOverrides.FalloffDistance = 900.f;
	LoopAudio->AttenuationOverrides.AttenuationShapeExtents = FVector(60.f);
	// Oclusion: a traves de paredes y puertas cerradas el sonido se apaga y pierde agudos.
	LoopAudio->AttenuationOverrides.bEnableOcclusion = true;
	LoopAudio->AttenuationOverrides.OcclusionTraceChannel = ECC_Visibility;
	LoopAudio->AttenuationOverrides.OcclusionLowPassFilterFrequency = 700.f;
	LoopAudio->AttenuationOverrides.OcclusionVolumeAttenuation = 0.35f;
	LoopAudio->AttenuationOverrides.OcclusionInterpolationTime = 0.25f;
	LoopAudio->AttenuationOverrides.bEnableReverbSend = true;


	Prompt = NSLOCTEXT("Vigilia", "TV", "Televisor");
}

void AVGTelevision::SetupScreen(UMaterialInterface* InScreenMaterial, int32 SlotIndex, FTransform PlaneRelativeTransform, FVector GlowRelativeLocation, FRotator GlowRelativeRotation, float ScreenWidth, float ScreenHeight)
{
	Modify();
	ScreenPlane->Modify();
	ScreenGlow->Modify();
	Mesh->Modify();

	ScreenMaterial = InScreenMaterial;
	ScreenMaterialSlot = SlotIndex;

	if (SlotIndex >= 0)
	{
		Mesh->SetMaterial(SlotIndex, InScreenMaterial);
		ScreenPlane->SetVisibility(false);
	}
	else
	{
		ScreenPlane->SetRelativeTransform(PlaneRelativeTransform);
		ScreenPlane->SetMaterial(0, InScreenMaterial);
		ScreenPlane->SetVisibility(true);
	}

	ScreenGlow->SetRelativeLocationAndRotation(GlowRelativeLocation, GlowRelativeRotation);
	ScreenGlow->SetSourceWidth(FMath::Max(ScreenWidth, 5.f));
	ScreenGlow->SetSourceHeight(FMath::Max(ScreenHeight, 5.f));
}

void AVGTelevision::BeginPlay()
{
	Super::BeginPlay();

	if (ScreenMaterial)
	{
		if (ScreenMaterialSlot >= 0 && ScreenMaterialSlot < Mesh->GetNumMaterials())
		{
			ScreenMID = Mesh->CreateDynamicMaterialInstance(ScreenMaterialSlot, ScreenMaterial);
		}
		else if (ScreenPlane->GetStaticMesh())
		{
			ScreenMID = ScreenPlane->CreateDynamicMaterialInstance(0, ScreenMaterial);
		}
	}
	WarmUp = bOn ? 1.f : 0.f;
	ApplyState();
	if (bOn && StaticLoopSound)
	{
		LoopAudio->SetSound(StaticLoopSound);
		LoopAudio->Play();
	}
	SetActorTickEnabled(bOn);
}

FText AVGTelevision::GetInteractionPrompt_Implementation(AActor* Interactor) const
{
	return bOn ? NSLOCTEXT("Vigilia", "TVOff", "Apagar televisor") : NSLOCTEXT("Vigilia", "TVOn", "Encender televisor");
}

void AVGTelevision::Interact_Implementation(AActor* Interactor)
{
	SetOn(!bOn);
	Super::Interact_Implementation(Interactor);
}

void AVGTelevision::SetOn(bool bInOn, bool bPlaySound)
{
	if (bOn == bInOn)
	{
		return;
	}
	bOn = bInOn;
	if (bPlaySound)
	{
		PlayLocalSound(PowerSound, 1.f, bOn ? 1.f : 0.85f);
	}
	if (bOn)
	{
		WarmUp = 0.f;
		if (StaticLoopSound)
		{
			LoopAudio->SetSound(StaticLoopSound);
			LoopAudio->FadeIn(0.35f, 1.f);
		}
	}
	else
	{
		LoopAudio->FadeOut(0.08f, 0.f);
	}
	SetActorTickEnabled(true);
}

void AVGTelevision::ApplyState()
{
	const float Power = bOn ? WarmUp : 0.f;
	if (ScreenMID)
	{
		ScreenMID->SetScalarParameterValue(TEXT("Power"), Power);
	}
	// La nieve de un CRT nunca ilumina de forma constante.
	const float Noise = 0.78f + 0.22f * FMath::FRand();
	ScreenGlow->SetIntensity(GlowLumens * Power * Noise);
	ScreenGlow->SetVisibility(Power > 0.01f);
}

void AVGTelevision::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (bOn)
	{
		WarmUp = FMath::Min(1.f, WarmUp + DeltaSeconds / 0.9f);
	}
	ApplyState();
	if (!bOn)
	{
		SetActorTickEnabled(false);
	}
}
