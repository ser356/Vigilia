#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "VGPlayerCharacter.generated.h"

class UCameraComponent;
class USpotLightComponent;
class UPointLightComponent;
class UInputAction;
class UInputMappingContext;
class UVGInteractionComponent;
class AVGExaminable;
class USoundBase;
struct FInputActionValue;

/** Personaje en primera persona: andar/correr, mirar, interactuar, examinar y linterna. */
UCLASS(Config = Game)
class VIGILIA_API AVGPlayerCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	AVGPlayerCharacter();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Examine")
	void BeginExamine(AVGExaminable* Item);

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Examine")
	void EndExamine();

	UFUNCTION(BlueprintPure, Category = "Vigilia|Examine")
	AVGExaminable* GetExaminedItem() const { return ExaminedItem; }

	UFUNCTION(BlueprintPure, Category = "Vigilia")
	UVGInteractionComponent* GetInteraction() const { return Interaction; }

	/** Consola: VGSetSensitivity 0.8  (se guarda en la configuracion del juego). */
	UFUNCTION(Exec, BlueprintCallable, Category = "Vigilia|Settings")
	void VGSetSensitivity(float NewSensitivity);

	/** La linterna parpadea y se apaga durante Duration segundos (no se puede encender mientras). */
	UFUNCTION(BlueprintCallable, Category = "Vigilia|Flashlight")
	void FailFlashlight(float Duration);

	/** Consola: VGQuality 0..3 (bajo, medio, alto, epico). Se guarda para la proxima partida. */
	UFUNCTION(Exec, BlueprintCallable, Category = "Vigilia|Settings")
	void VGQuality(int32 Level);

	/** Consola: VGInvertY 1 */
	UFUNCTION(Exec, BlueprintCallable, Category = "Vigilia|Settings")
	void VGInvertY(bool bInvert);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<UCameraComponent> Camera;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<USpotLightComponent> Flashlight;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<UVGInteractionComponent> Interaction;

	/** Luz suave junto a la camara que solo se enciende al examinar un objeto. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<UPointLightComponent> InspectLight;

	/** Lumenes de la luz de examen para un objeto a 40 cm (se ajusta con la distancia). */
	UPROPERTY(Config, EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Examine")
	float InspectLumens = 6.f;

	UPROPERTY(Config, EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Settings")
	float MouseSensitivity = 1.f;

	UPROPERTY(Config, EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Settings")
	bool bInvertLookY = false;

	UPROPERTY(Config, EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Movement")
	float WalkSpeed = 250.f;

	UPROPERTY(Config, EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Movement")
	float RunSpeed = 430.f;

	/** Distancia recorrida entre pasos al andar (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	float StepDistance = 72.f;

	UPROPERTY(Config, EditAnywhere, Category = "Vigilia|Audio")
	TArray<FSoftObjectPath> FootstepSounds;

	UPROPERTY(Config, EditAnywhere, Category = "Vigilia|Audio")
	FSoftObjectPath FlashlightSound;

private:
	void BuildInput();
	void OnMoveForward(const FInputActionValue& Value);
	void OnMoveRight(const FInputActionValue& Value);
	void OnLook(const FInputActionValue& Value);
	void OnInteract(const FInputActionValue& Value);
	void OnCancel(const FInputActionValue& Value);
	void OnRunStarted(const FInputActionValue& Value);
	void OnRunCompleted(const FInputActionValue& Value);
	void OnFlashlight(const FInputActionValue& Value);
	void UpdateFootsteps(float DeltaSeconds);
	void UpdateExamine();

	UPROPERTY(Transient)
	TObjectPtr<UInputMappingContext> MappingContext;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> MoveForwardAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> MoveRightAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> LookAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> InteractAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> CancelAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> RunAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> FlashlightAction;

	UPROPERTY(Transient)
	TObjectPtr<AVGExaminable> ExaminedItem;
	UPROPERTY(Transient)
	TArray<TObjectPtr<USoundBase>> LoadedFootsteps;
	UPROPERTY(Transient)
	TObjectPtr<USoundBase> LoadedFlashlightSound;

	void UpdateFlashlightFailure(float DeltaSeconds);
	bool bFlashlightBeforeExamine = false;
	float FlashlightFailTime = 0.f;
	float FlashlightFailTotal = 0.f;
	float FlashlightFlickerTimer = 0.f;
	bool bFlashlightWasOn = false;

	FQuat ExamineRotation = FQuat::Identity;
	FVector ExamineCenterLocal = FVector::ZeroVector;
	float ExamineDistance = 45.f;
	float StepAccumulator = 0.f;
	int32 LastStepIndex = -1;
};
