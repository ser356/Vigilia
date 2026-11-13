#pragma once

#include "CoreMinimal.h"
#include "VGInteractableActor.h"
#include "VGTelevision.generated.h"

class URectLightComponent;
class UMaterialInterface;
class UMaterialInstanceDynamic;

/** Televisor CRT: pantalla emisiva con nieve, luz parpadeante y audio de estatica. */
UCLASS()
class VIGILIA_API AVGTelevision : public AVGInteractableActor
{
	GENERATED_BODY()

public:
	AVGTelevision();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual FText GetInteractionPrompt_Implementation(AActor* Interactor) const override;
	virtual void Interact_Implementation(AActor* Interactor) override;

	UFUNCTION(BlueprintCallable, Category = "Vigilia|TV")
	void SetOn(bool bInOn, bool bPlaySound = true);

	UFUNCTION(BlueprintPure, Category = "Vigilia|TV")
	bool IsOn() const { return bOn; }

	/**
	 * Configura la pantalla. Si SlotIndex >= 0 se sustituye ese material de la malla;
	 * si no, se usa el plano auxiliar ScreenPlane con la transformacion indicada.
	 */
	UFUNCTION(BlueprintCallable, Category = "Vigilia|TV")
	void SetupScreen(UMaterialInterface* InScreenMaterial, int32 SlotIndex, FTransform PlaneRelativeTransform, FVector GlowRelativeLocation, FRotator GlowRelativeRotation, float ScreenWidth, float ScreenHeight);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<UStaticMeshComponent> ScreenPlane;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<URectLightComponent> ScreenGlow;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<UAudioComponent> LoopAudio;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|TV")
	bool bOn = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|TV")
	TObjectPtr<UMaterialInterface> ScreenMaterial;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|TV")
	int32 ScreenMaterialSlot = -1;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|TV")
	float GlowLumens = 160.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	TObjectPtr<USoundBase> PowerSound;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	TObjectPtr<USoundBase> StaticLoopSound;

private:
	void ApplyState();

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> ScreenMID;

	float WarmUp = 0.f;
};
