import * as Haptics from "expo-haptics";

export async function hapticLand(): Promise<void> {
  try {
    await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
  } catch {
    /* haptics unavailable on simulator */
  }
}

export async function hapticMiss(): Promise<void> {
  try {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
  } catch {
    /* haptics unavailable on simulator */
  }
}
