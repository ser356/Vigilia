#include "VGAmbientAudio.h"
#include "VGStatics.h"
#include "Components/AudioComponent.h"
#include "Kismet/GameplayStatics.h"
#include "GameFramework/Pawn.h"
#include "TimerManager.h"

AVGAmbientAudio::AVGAmbientAudio()
{
	Bed = CreateDefaultSubobject<UAudioComponent>(TEXT("Bed"));
	SetRootComponent(Bed);
	Bed->bAutoActivate = true;
	Bed->bAllowSpatialization = false;
	Bed->bIsUISound = false;
}

void AVGAmbientAudio::SetBedSound(USoundBase* Sound, float Volume)
{
	Bed->Modify();
	Bed->SetSound(Sound);
	Bed->SetVolumeMultiplier(Volume);
}

void AVGAmbientAudio::AddRandomSound(USoundBase* Sound)
{
	if (Sound)
	{
		Modify();
		RandomSounds.AddUnique(Sound);
	}
}

void AVGAmbientAudio::BeginPlay()
{
	Super::BeginPlay();
	ScheduleNext();
}

void AVGAmbientAudio::ScheduleNext()
{
	const float Delay = FMath::FRandRange(MinInterval, FMath::Max(MinInterval, MaxInterval));
	GetWorldTimerManager().SetTimer(Timer, this, &AVGAmbientAudio::PlayRandom, Delay, false);
}

void AVGAmbientAudio::PlayRandom()
{
	const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0);
	if (Pawn && RandomSounds.Num() > 0)
	{
		USoundBase* Sound = RandomSounds[FMath::RandRange(0, RandomSounds.Num() - 1)];
		// Siempre fuera de la habitacion: detras de paredes, arriba o en el pasillo.
		const float Angle = FMath::FRandRange(0.f, 2.f * PI);
		const float Distance = FMath::FRandRange(MinDistance, MaxDistance);
		const FVector Offset(FMath::Cos(Angle) * Distance, FMath::Sin(Angle) * Distance, FMath::FRandRange(-40.f, 260.f));
		UVGStatics::PlaySpatialSound(this, Sound, Pawn->GetActorLocation() + Offset, RandomVolume, FMath::FRandRange(0.9f, 1.08f));
	}
	ScheduleNext();
}
