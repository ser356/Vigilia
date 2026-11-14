#pragma once

#include "CoreMinimal.h"
#include "VGInteractableActor.h"
#include "VGLamp.generated.h"

class UPointLightComponent;

/** Lampara conmutable con parpadeo controlable por eventos. */
UCLASS()
class VIGILIA_API AVGLamp : public AVGInteractableActor
{
	GENERATED_BODY()

public:
	AVGLamp();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual FText GetInteractionPrompt_Implementation(AActor* Interactor) const override;
	virtual void Interact_Implementation(AActor* Interactor) override;

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Lamp")
	void SetOn(bool bInOn, bool bPlaySound = true);

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Lamp")
	void Toggle() { SetOn(!bOn); }

	/** Parpadea durante Duration segundos y termina en el estado indicado. */
	UFUNCTION(BlueprintCallable, Category = "Vigilia|Lamp")
	void Flicker(float Duration = 1.5f, bool bEndOn = true);

	UFUNCTION(BlueprintPure, Category = "Vigilia|Lamp")
	bool IsOn() const { return bOn; }

	/** Tinte de la luz (desactiva la temperatura de color). */
	UFUNCTION(BlueprintCallable, Category = "Vigilia|Lamp")
	void SetColor(FLinearColor Color);

	/** Configura la bombilla (lumenes, temperatura en Kelvin y posicion local). */
	UFUNCTION(BlueprintCallable, Category = "Vigilia|Lamp")
	void SetupLight(FVector RelativeLocation, float Lumens, float Temperature, float AttenuationRadius);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<UPointLightComponent> Light;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Lamp")
	bool bOn = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Lamp")
	float OnIntensity = 800.f;

	/** Si es false, la lampara solo se controla desde interruptores/eventos. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Lamp")
	bool bDirectlyInteractable = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	TObjectPtr<USoundBase> SwitchSound;

private:
	void ApplyState(float IntensityScale);

	float FlickerTimeLeft = 0.f;
	float NextFlickerChange = 0.f;
	bool bFlickerEndOn = true;
};
