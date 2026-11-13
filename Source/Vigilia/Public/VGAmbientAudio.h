#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VGAmbientAudio.generated.h"

class UAudioComponent;
class USoundBase;

/** Tono de sala continuo + sonidos domesticos aleatorios espacializados alrededor del jugador. */
UCLASS()
class VIGILIA_API AVGAmbientAudio : public AActor
{
	GENERATED_BODY()

public:
	AVGAmbientAudio();

	virtual void BeginPlay() override;

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Audio")
	void SetBedSound(USoundBase* Sound, float Volume);

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Audio")
	void AddRandomSound(USoundBase* Sound);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<UAudioComponent> Bed;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	TArray<TObjectPtr<USoundBase>> RandomSounds;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	float MinInterval = 14.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	float MaxInterval = 38.f;

	/** Distancia al jugador a la que suenan los sonidos aleatorios (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	float MinDistance = 350.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	float MaxDistance = 700.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	float RandomVolume = 0.55f;

private:
	void ScheduleNext();
	void PlayRandom();

	FTimerHandle Timer;
};
