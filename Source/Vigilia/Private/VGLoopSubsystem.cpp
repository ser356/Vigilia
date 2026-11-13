#include "VGLoopSubsystem.h"
#include "Engine/World.h"

void UVGLoopSubsystem::AdvanceLoop()
{
	++LoopCount;
	OnLoopAdvanced.Broadcast(LoopCount);
}

void UVGLoopSubsystem::ShowMessage(const FText& Text, float Duration)
{
	Message = Text;
	MessageStart = GetWorld()->GetTimeSeconds();
	MessageEnd = MessageStart + FMath::Max(Duration, 0.5f);
}

FText UVGLoopSubsystem::GetMessage(float& OutAlpha) const
{
	const double Now = GetWorld()->GetTimeSeconds();
	if (Message.IsEmpty() || Now > MessageEnd)
	{
		OutAlpha = 0.f;
		return FText::GetEmpty();
	}
	// Aparece y desaparece en 1 s.
	const float In = static_cast<float>(FMath::Clamp(Now - MessageStart, 0.0, 1.0));
	const float Out = static_cast<float>(FMath::Clamp(MessageEnd - Now, 0.0, 1.0));
	OutAlpha = FMath::Min(In, Out);
	return Message;
}
