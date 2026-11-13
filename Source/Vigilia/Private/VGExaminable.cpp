#include "VGExaminable.h"
#include "VGPlayerCharacter.h"
#include "Components/StaticMeshComponent.h"

AVGExaminable::AVGExaminable()
{
	Prompt = NSLOCTEXT("Vigilia", "Examine", "Examinar");
}

FText AVGExaminable::GetInteractionPrompt_Implementation(AActor* Interactor) const
{
	if (DisplayName.IsEmpty())
	{
		return Prompt;
	}
	return FText::Format(NSLOCTEXT("Vigilia", "ExamineFmt", "Examinar {0}"), DisplayName);
}

void AVGExaminable::Interact_Implementation(AActor* Interactor)
{
	if (AVGPlayerCharacter* Player = Cast<AVGPlayerCharacter>(Interactor))
	{
		Player->BeginExamine(this);
	}
	Super::Interact_Implementation(Interactor);
}

float AVGExaminable::GetExamineRadius() const
{
	FVector Origin, Extent;
	GetActorBounds(false, Origin, Extent, true);
	return FMath::Max(static_cast<float>(Extent.Size()), 4.f);
}

void AVGExaminable::BeginExamine()
{
	if (bBeingExamined)
	{
		return;
	}
	bBeingExamined = true;
	RestTransform = GetActorTransform();
	SetActorEnableCollision(false);
	PlayLocalSound(PickUpSound);
}

void AVGExaminable::EndExamine()
{
	if (!bBeingExamined)
	{
		return;
	}
	bBeingExamined = false;
	DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
	SetActorTransform(RestTransform);
	SetActorEnableCollision(true);
	PlayLocalSound(PutDownSound);
}
