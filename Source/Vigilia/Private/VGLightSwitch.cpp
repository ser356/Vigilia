#include "VGLightSwitch.h"
#include "VGLamp.h"

AVGLightSwitch::AVGLightSwitch()
{
	Prompt = NSLOCTEXT("Vigilia", "Switch", "Interruptor");
}

FText AVGLightSwitch::GetInteractionPrompt_Implementation(AActor* Interactor) const
{
	for (const AVGLamp* Lamp : Targets)
	{
		if (Lamp && Lamp->IsOn())
		{
			return NSLOCTEXT("Vigilia", "SwitchOff", "Apagar la luz");
		}
	}
	return NSLOCTEXT("Vigilia", "SwitchOn", "Encender la luz");
}

void AVGLightSwitch::AddTarget(AVGLamp* Lamp)
{
	if (Lamp)
	{
		Modify();
		Targets.AddUnique(Lamp);
	}
}

void AVGLightSwitch::Interact_Implementation(AActor* Interactor)
{
	bool bAnyOn = false;
	for (const AVGLamp* Lamp : Targets)
	{
		bAnyOn |= (Lamp && Lamp->IsOn());
	}
	for (AVGLamp* Lamp : Targets)
	{
		if (Lamp)
		{
			Lamp->SetOn(!bAnyOn, false);
		}
	}
	PlayLocalSound(SwitchSound);
	Super::Interact_Implementation(Interactor);
}
