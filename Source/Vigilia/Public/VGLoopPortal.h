#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VGLoopPortal.generated.h"

class UBoxComponent;
class USoundBase;

/**
 * Al entrar el jugador, lo traslada a Destination conservando su posicion y orientacion relativas
 * (con un parpadeo a negro) y avanza el contador del bucle. Base de la estructura tipo P.T.
 */
UCLASS()
class VIGILIA_API AVGLoopPortal : public AActor
{
	GENERATED_BODY()

public:
	AVGLoopPortal();

	virtual void BeginPlay() override;

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Loop")
	void SetBoxExtent(FVector Extent);

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Loop")
	void SetDestination(AActor* InDestination);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<UBoxComponent> Box;

	UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Vigilia|Loop")
	TObjectPtr<AActor> Destination;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Loop")
	TObjectPtr<USoundBase> TeleportSound;

	/** Puerta que se cierra al saltar (la del fondo del pasillo), para que el bucle no se vea. */
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Vigilia|Loop")
	TObjectPtr<AActor> DoorToClose;

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Loop")
	void SetDoorToClose(AActor* InDoor) { Modify(); DoorToClose = InDoor; }

	/** Duracion del fundido desde negro tras el salto. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Loop")
	float FadeInTime = 0.9f;

private:
	UFUNCTION()
	void HandleOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult);

	double LastTeleport = -100.0;
};
