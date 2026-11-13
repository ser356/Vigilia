#pragma once

#include "CoreMinimal.h"
#include "VGInteractableActor.h"
#include "VGPhone.generated.h"

class AVGEventTrigger;

/** Telefono fijo: suena cuando un evento lo pide; al contestar reproduce la llamada y dispara AnswerEvent. */
UCLASS()
class VIGILIA_API AVGPhone : public AVGInteractableActor
{
	GENERATED_BODY()

public:
	AVGPhone();

	virtual FText GetInteractionPrompt_Implementation(AActor* Interactor) const override;
	virtual bool CanInteract_Implementation(AActor* Interactor) const override;
	virtual void Interact_Implementation(AActor* Interactor) override;

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Phone")
	void Ring();

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Phone")
	void StopRinging();

	UFUNCTION(BlueprintPure, Category = "Vigilia|Phone")
	bool IsRinging() const { return bRinging; }

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	TObjectPtr<USoundBase> RingSound;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	TObjectPtr<USoundBase> AnswerSound;

	/** Segundos que suena antes de colgar solo. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Phone")
	float RingDuration = 30.f;

	/** Evento que se dispara al contestar. */
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Vigilia|Phone")
	TObjectPtr<AVGEventTrigger> AnswerEvent;

	/** Evento que se dispara si deja de sonar sin que contestes. */
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Vigilia|Phone")
	TObjectPtr<AVGEventTrigger> MissedEvent;

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Phone")
	void SetEvents(AVGEventTrigger* InAnswerEvent, AVGEventTrigger* InMissedEvent);

private:
	void OnRingTimeout();

	bool bRinging = false;
	bool bAnswered = false;
	FTimerHandle RingTimer;
};
