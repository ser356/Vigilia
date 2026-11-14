#include "VGLamp.h"
#include "Components/PointLightComponent.h"

AVGLamp::AVGLamp()
{
	Light = CreateDefaultSubobject<UPointLightComponent>(TEXT("Light"));
	Light->SetupAttachment(Root);
	Light->SetMobility(EComponentMobility::Movable);
	Light->SetIntensityUnits(ELightUnits::Lumens);
	Light->SetIntensity(0.f);
	Light->SetVisibility(false);
	Light->bUseTemperature = true;
	Light->Temperature = 2700.f;
	Light->SetAttenuationRadius(700.f);
	Light->SetSourceRadius(4.f);
	Light->SetSoftSourceRadius(8.f);
	Light->SetCastShadows(true);
	// La pantalla de la lampara no debe bloquear su propia bombilla.
	Mesh->SetCastShadow(false);
	Prompt = NSLOCTEXT("Vigilia", "Lamp", "Lampara");
}

void AVGLamp::SetupLight(FVector RelativeLocation, float Lumens, float Temperature, float AttenuationRadius)
{
	Modify();
	Light->Modify();
	OnIntensity = Lumens;
	Light->SetRelativeLocation(RelativeLocation);
	Light->SetIntensityUnits(ELightUnits::Lumens);
	ApplyState(1.f);
	Light->bUseTemperature = true;
	Light->SetTemperature(Temperature);
	Light->SetAttenuationRadius(AttenuationRadius);
}

void AVGLamp::BeginPlay()
{
	Super::BeginPlay();
	ApplyState(1.f);
}

FText AVGLamp::GetInteractionPrompt_Implementation(AActor* Interactor) const
{
	return bOn ? NSLOCTEXT("Vigilia", "LampOff", "Apagar lampara") : NSLOCTEXT("Vigilia", "LampOn", "Encender lampara");
}

void AVGLamp::Interact_Implementation(AActor* Interactor)
{
	if (bDirectlyInteractable)
	{
		Toggle();
	}
	Super::Interact_Implementation(Interactor);
}

void AVGLamp::SetOn(bool bInOn, bool bPlaySound)
{
	bOn = bInOn;
	FlickerTimeLeft = 0.f;
	SetActorTickEnabled(false);
	ApplyState(1.f);
	if (bPlaySound)
	{
		PlayLocalSound(SwitchSound, 1.f, bOn ? 1.f : 0.92f);
	}
}

void AVGLamp::Flicker(float Duration, bool bEndOn)
{
	FlickerTimeLeft = Duration;
	NextFlickerChange = 0.f;
	bFlickerEndOn = bEndOn;
	SetActorTickEnabled(true);
}

void AVGLamp::ApplyState(float IntensityScale)
{
	const float Scale = bOn ? IntensityScale : 0.f;
	Light->SetIntensity(OnIntensity * Scale);
	Light->SetVisibility(Scale > 0.001f);
}

void AVGLamp::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	FlickerTimeLeft -= DeltaSeconds;
	if (FlickerTimeLeft <= 0.f)
	{
		SetOn(bFlickerEndOn, false);
		return;
	}
	NextFlickerChange -= DeltaSeconds;
	if (NextFlickerChange <= 0.f)
	{
		NextFlickerChange = FMath::FRandRange(0.03f, 0.16f);
		const bool bWasOn = bOn;
		bOn = true;
		ApplyState(FMath::FRand() < 0.35f ? 0.f : FMath::FRandRange(0.25f, 1.f));
		bOn = bWasOn;
	}
}

void AVGLamp::SetColor(FLinearColor Color)
{
	Light->bUseTemperature = false;
	Light->SetLightColor(Color);
}
