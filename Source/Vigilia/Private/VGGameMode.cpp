#include "VGGameMode.h"
#include "VGPlayerCharacter.h"
#include "VGInteractionComponent.h"
#include "VGExaminable.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"

AVGGameMode::AVGGameMode()
{
	DefaultPawnClass = AVGPlayerCharacter::StaticClass();
	HUDClass = AVGHUD::StaticClass();
}

void AVGHUD::DrawCentered(const FString& Text, float Y, float Scale, const FLinearColor& Color)
{
	UFont* Font = GEngine ? GEngine->GetMediumFont() : nullptr;
	if (!Font || Text.IsEmpty())
	{
		return;
	}
	float W = 0.f, H = 0.f;
	GetTextSize(Text, W, H, Font, Scale);
	const float X = (Canvas->ClipX - W) * 0.5f;
	DrawText(Text, FLinearColor(0.f, 0.f, 0.f, 0.75f * Color.A), X + 1.f, Y + 1.f, Font, Scale);
	DrawText(Text, Color, X, Y, Font, Scale);
}

void AVGHUD::DrawHUD()
{
	Super::DrawHUD();

	const AVGPlayerCharacter* Player = Cast<AVGPlayerCharacter>(GetOwningPawn());
	if (!Player || !Canvas)
	{
		return;
	}

	const float CX = Canvas->ClipX * 0.5f;
	const float CY = Canvas->ClipY * 0.5f;
	const float UIScale = FMath::Max(Canvas->ClipY / 1080.f, 0.5f);

	if (const AVGExaminable* Item = Player->GetExaminedItem())
	{
		if (!Item->ExamineText.IsEmpty())
		{
			DrawCentered(Item->ExamineText.ToString(), Canvas->ClipY * 0.80f, 1.25f * UIScale, FLinearColor(0.9f, 0.9f, 0.86f, 1.f));
		}
		DrawCentered(TEXT("Mueve el raton para girar   -   [E] / [Clic derecho] Dejar"), Canvas->ClipY * 0.92f, 1.0f * UIScale, FLinearColor(0.7f, 0.7f, 0.7f, 0.8f));
		return;
	}

	const UVGInteractionComponent* Interaction = Player->GetInteraction();
	const bool bHasFocus = Interaction && Interaction->GetFocusedActor() != nullptr;

	// Punto de mira discreto: crece ligeramente al enfocar algo interactuable.
	const float Dot = (bHasFocus ? 3.f : 1.5f) * UIScale;
	DrawRect(FLinearColor(1.f, 1.f, 1.f, bHasFocus ? 0.85f : 0.35f), CX - Dot, CY - Dot, Dot * 2.f, Dot * 2.f);

	if (bHasFocus)
	{
		const FString Prompt = FString::Printf(TEXT("[E]  %s"), *Interaction->GetFocusedPrompt().ToString());
		DrawCentered(Prompt, CY + 34.f * UIScale, 1.15f * UIScale, FLinearColor(0.92f, 0.92f, 0.88f, 0.95f));
	}
}
