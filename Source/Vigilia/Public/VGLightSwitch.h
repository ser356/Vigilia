#pragma once

#include "CoreMinimal.h"
#include "VGInteractableActor.h"
#include "VGLightSwitch.generated.h"

class AVGLamp;

/** Interruptor de pared que conmuta una o varias lamparas. */
UCLASS()
class VIGILIA_API AVGLightSwitch : public AVGInteractableActor
{
	GENERATED_BODY()

public:
	AVGLightSwitch();

	virtual FText GetInteractionPrompt_Implementation(AActor* Interactor) const override;
	virtual void Interact_Implementation(AActor* Interactor) override;

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Switch")
	void AddTarget(AVGLamp* Lamp);

	UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Vigilia|Switch")
	TArray<TObjectPtr<AVGLamp>> Targets;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	TObjectPtr<USoundBase> SwitchSound;
};
