#pragma once

#include "CoreMinimal.h"
#include "UObject/Interface.h"
#include "VGInteractable.generated.h"

UINTERFACE(MinimalAPI, BlueprintType)
class UVGInteractable : public UInterface
{
	GENERATED_BODY()
};

/** Contrato unico para cualquier cosa con la que el jugador pueda interactuar. */
class VIGILIA_API IVGInteractable
{
	GENERATED_BODY()

public:
	/** Texto que se muestra en el HUD ("Abrir puerta", "Encender lampara"...). */
	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "Vigilia|Interaction")
	FText GetInteractionPrompt(AActor* Interactor) const;

	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "Vigilia|Interaction")
	bool CanInteract(AActor* Interactor) const;

	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "Vigilia|Interaction")
	void Interact(AActor* Interactor);

	/** Notifica que el jugador empieza/deja de mirar el objeto. */
	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "Vigilia|Interaction")
	void SetFocused(bool bFocused);
};
