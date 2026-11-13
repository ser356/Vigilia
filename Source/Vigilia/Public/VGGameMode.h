#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "VGGameMode.generated.h"

UCLASS()
class VIGILIA_API AVGGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AVGGameMode();
};

/** HUD minimo dibujado en Canvas: punto de mira, indicador de interaccion y texto de examen. */
UCLASS()
class VIGILIA_API AVGHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;

private:
	void DrawCentered(const FString& Text, float Y, float Scale, const FLinearColor& Color);
};
