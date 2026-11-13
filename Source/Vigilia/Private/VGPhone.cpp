#include "VGPhone.h"
#include "VGEventTrigger.h"
#include "Components/AudioComponent.h"
#include "TimerManager.h"
#include "Engine/World.h"

AVGPhone::AVGPhone()
{
	Prompt = NSLOCTEXT("Vigilia", "Phone", "Telefono");
}

void AVGPhone::SetEvents(AVGEventTrigger* InAnswerEvent, AVGEventTrigger* InMissedEvent)
{
	Modify();
	AnswerEvent = InAnswerEvent;
	MissedEvent = InMissedEvent;
}

FText AVGPhone::GetInteractionPrompt_Implementation(AActor* Interactor) const
{
	return NSLOCTEXT("Vigilia", "PhoneAnswer", "Contestar");
}

bool AVGPhone::CanInteract_Implementation(AActor* Interactor) const
{
	return bInteractionEnabled && bRinging;
}

void AVGPhone::Ring()
{
	if (bRinging || bAnswered)
	{
		return;
	}
	bRinging = true;
	PlayLocalSound(RingSound, 1.f);
	GetWorldTimerManager().SetTimer(RingTimer, this, &AVGPhone::OnRingTimeout, RingDuration, false);
}

void AVGPhone::StopRinging()
{
	bRinging = false;
	GetWorldTimerManager().ClearTimer(RingTimer);
	if (Audio)
	{
		Audio->Stop();
	}
}

void AVGPhone::OnRingTimeout()
{
	StopRinging();
	if (MissedEvent)
	{
		MissedEvent->Fire();
	}
}

void AVGPhone::Interact_Implementation(AActor* Interactor)
{
	if (!bRinging)
	{
		return;
	}
	StopRinging();
	bAnswered = true;
	PlayLocalSound(AnswerSound, 1.f);
	if (AnswerEvent)
	{
		AnswerEvent->Fire();
	}
	Super::Interact_Implementation(Interactor);
}
