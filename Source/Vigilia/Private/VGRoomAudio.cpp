#include "VGRoomAudio.h"
#include "Components/BoxComponent.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/ReverbEffect.h"

AVGRoomAudio::AVGRoomAudio()
{
	Box = CreateDefaultSubobject<UBoxComponent>(TEXT("Box"));
	SetRootComponent(Box);
	Box->SetBoxExtent(FVector(200.f, 200.f, 130.f));
	Box->SetCollisionProfileName(TEXT("Trigger"));
	Box->SetGenerateOverlapEvents(true);
}

void AVGRoomAudio::SetBoxExtent(FVector Extent)
{
	Box->Modify();
	Box->SetBoxExtent(Extent);
}

void AVGRoomAudio::SetupReverb(float InDecayTime, float InBrightness, float InGain)
{
	Modify();
	DecayTime = InDecayTime;
	Brightness = InBrightness;
	Gain = InGain;
}

void AVGRoomAudio::BeginPlay()
{
	Super::BeginPlay();

	Reverb = NewObject<UReverbEffect>(this);
	Reverb->Density = 0.9f;
	Reverb->Diffusion = 0.85f;
	Reverb->Gain = FMath::Clamp(Gain, 0.f, 0.99f);
	Reverb->GainHF = FMath::Lerp(0.35f, 0.9f, FMath::Clamp(Brightness, 0.f, 1.f));
	Reverb->DecayTime = FMath::Clamp(DecayTime, 0.1f, 20.f);
	Reverb->DecayHFRatio = FMath::Lerp(0.4f, 1.1f, FMath::Clamp(Brightness, 0.f, 1.f));
	Reverb->ReflectionsGain = 0.25f + 0.3f * Brightness;
	Reverb->ReflectionsDelay = 0.006f;
	Reverb->LateGain = 1.1f;
	Reverb->LateDelay = 0.012f;
	Reverb->AirAbsorptionGainHF = 0.994f;

	Box->OnComponentBeginOverlap.AddDynamic(this, &AVGRoomAudio::HandleOverlap);

	// Si el jugador empieza dentro, se activa ya.
	if (const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0))
	{
		const FVector Local = Box->GetComponentTransform().InverseTransformPosition(Pawn->GetActorLocation());
		const FVector E = Box->GetUnscaledBoxExtent();
		if (FMath::Abs(Local.X) <= E.X && FMath::Abs(Local.Y) <= E.Y && FMath::Abs(Local.Z) <= E.Z)
		{
			Activate();
		}
	}
}

void AVGRoomAudio::HandleOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult)
{
	const APawn* Pawn = Cast<APawn>(OtherActor);
	if (Pawn && Pawn->IsPlayerControlled())
	{
		Activate();
	}
}

void AVGRoomAudio::Activate()
{
	if (Reverb)
	{
		// Mismo tag para todas las estancias: la nueva sustituye a la anterior con un fundido.
		UGameplayStatics::ActivateReverbEffect(this, Reverb, TEXT("VGRoom"), 1.f, 1.f, 0.6f);
	}
}
