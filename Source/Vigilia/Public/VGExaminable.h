#pragma once

#include "CoreMinimal.h"
#include "VGInteractableActor.h"
#include "VGExaminable.generated.h"

/** Objeto pequeno que el jugador puede coger, girar y volver a dejar. */
UCLASS()
class VIGILIA_API AVGExaminable : public AVGInteractableActor
{
	GENERATED_BODY()

public:
	AVGExaminable();

	virtual FText GetInteractionPrompt_Implementation(AActor* Interactor) const override;
	virtual void Interact_Implementation(AActor* Interactor) override;

	/** Llamado por el jugador al empezar/terminar el examen. */
	void BeginExamine();
	void EndExamine();

	UFUNCTION(BlueprintPure, Category = "Vigilia|Examine")
	float GetExamineRadius() const;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Examine")
	FText DisplayName;

	/** Texto que se muestra mientras se examina. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Examine", meta = (MultiLine = true))
	FText ExamineText;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	TObjectPtr<USoundBase> PickUpSound;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	TObjectPtr<USoundBase> PutDownSound;

private:
	FTransform RestTransform;
	bool bBeingExamined = false;
};
