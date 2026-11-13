#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VGRoomAudio.generated.h"

class UBoxComponent;
class UReverbEffect;

/** Acustica de una estancia: al entrar el jugador se activa su reverberacion (bano con eco, dormitorio seco...). */
UCLASS()
class VIGILIA_API AVGRoomAudio : public AActor
{
	GENERATED_BODY()

public:
	AVGRoomAudio();

	virtual void BeginPlay() override;

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Audio")
	void SetBoxExtent(FVector Extent);

	/** Ajusta la reverberacion: tiempo de caida (s), brillo (0-1, superficies duras = alto) y nivel. */
	UFUNCTION(BlueprintCallable, Category = "Vigilia|Audio")
	void SetupReverb(float InDecayTime, float InBrightness, float InGain);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<UBoxComponent> Box;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	float DecayTime = 0.8f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	float Brightness = 0.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	float Gain = 0.35f;

private:
	UFUNCTION()
	void HandleOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult);

	void Activate();

	UPROPERTY(Transient)
	TObjectPtr<UReverbEffect> Reverb;
};
