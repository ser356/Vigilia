#pragma once

#include "CoreMinimal.h"
#include "VGInteractableActor.h"
#include "VGDoor.generated.h"

/**
 * Puerta batiente. Convencion local: la bisagra esta en el origen del actor,
 * la hoja cerrada se extiende a lo largo de +Y y el grosor queda centrado en X.
 */
UCLASS()
class VIGILIA_API AVGDoor : public AVGInteractableActor
{
	GENERATED_BODY()

public:
	AVGDoor();

	virtual void Tick(float DeltaSeconds) override;
	virtual FText GetInteractionPrompt_Implementation(AActor* Interactor) const override;
	virtual void Interact_Implementation(AActor* Interactor) override;

	/** Coloca la malla para que gire por su canto, sea cual sea su pivote o eje original. Devuelve (grosor, ancho, alto). */
	UFUNCTION(BlueprintCallable, Category = "Vigilia|Door")
	FVector SetupDoorMesh(UStaticMesh* InMesh, float TargetWidth = 0.f);

	/** DirectionSign: +1 o -1, hacia que lado abre. */
	UFUNCTION(BlueprintCallable, Category = "Vigilia|Door")
	void OpenDoor(float DirectionSign = 1.f, float DurationOverride = -1.f);

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Door")
	void CloseDoor(bool bSlam = false);

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Door")
	void SetLocked(bool bInLocked) { bLocked = bInLocked; }

	UFUNCTION(BlueprintPure, Category = "Vigilia|Door")
	bool IsOpen() const { return bOpen; }

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<USceneComponent> Hinge;

	/** Invierte el lado de la bisagra que se detecta automaticamente por la posicion del pomo. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Door")
	bool bSwapHingeSide = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Door")
	float OpenAngle = 96.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Door")
	float OpenDuration = 1.35f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Door")
	bool bLocked = false;

	/** Si es true abre siempre alejandose de quien interactua. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Door")
	bool bOpenAwayFromInteractor = true;

	/** Si es +1 o -1, la puerta abre SIEMPRE hacia ese lado (p. ej. hacia dentro de la habitacion,
	 *  como en una casa real, para no taponar el pasillo). 0 = abre alejandose del jugador. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Door")
	float PreferredOpenSign = 0.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	TObjectPtr<USoundBase> OpenSound;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	TObjectPtr<USoundBase> CloseSound;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	TObjectPtr<USoundBase> SlamSound;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	TObjectPtr<USoundBase> LockedSound;

private:
	void StartMove(float NewTargetYaw, float Duration);

	bool bOpen = false;
	float StartYaw = 0.f;
	float TargetYaw = 0.f;
	float MoveAlpha = 1.f;
	float MoveDuration = 1.f;
	bool bPendingCloseSound = false;
	bool bPendingSlam = false;
};
