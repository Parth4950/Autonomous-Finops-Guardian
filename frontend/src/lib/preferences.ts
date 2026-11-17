import { useCallback, useEffect, useState } from "react";

export interface NotificationPreferences {
  scanCompleted: boolean;
  scanFailed: boolean;
  anomalyAlerts: boolean;
}

const DEFAULT_PREFERENCES: NotificationPreferences = {
  scanCompleted: true,
  scanFailed: true,
  anomalyAlerts: true,
};

function storageKey(userId?: number | null): string {
  return userId ? `finops_notification_prefs_${userId}` : "finops_notification_prefs_default";
}

export function loadNotificationPreferences(userId?: number | null): NotificationPreferences {
  if (typeof window === "undefined") return DEFAULT_PREFERENCES;
  try {
    const raw = window.localStorage.getItem(storageKey(userId));
    if (!raw) return DEFAULT_PREFERENCES;
    const parsed = JSON.parse(raw) as Partial<NotificationPreferences>;
    return {
      scanCompleted:
        typeof parsed.scanCompleted === "boolean"
          ? parsed.scanCompleted
          : DEFAULT_PREFERENCES.scanCompleted,
      scanFailed:
        typeof parsed.scanFailed === "boolean"
          ? parsed.scanFailed
          : DEFAULT_PREFERENCES.scanFailed,
      anomalyAlerts:
        typeof parsed.anomalyAlerts === "boolean"
          ? parsed.anomalyAlerts
          : DEFAULT_PREFERENCES.anomalyAlerts,
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function saveNotificationPreferences(
  prefs: NotificationPreferences,
  userId?: number | null
): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(storageKey(userId), JSON.stringify(prefs));
    window.dispatchEvent(new CustomEvent("finops:notification-prefs-changed"));
  } catch {
    // Ignore storage write failures
  }
}

export function useNotificationPreferences(userId?: number | null) {
  const [preferences, setPreferences] = useState<NotificationPreferences>(() =>
    loadNotificationPreferences(userId)
  );

  useEffect(() => {
    setPreferences(loadNotificationPreferences(userId));
  }, [userId]);

  useEffect(() => {
    const onSync = () => setPreferences(loadNotificationPreferences(userId));
    window.addEventListener("finops:notification-prefs-changed", onSync);
    return () => window.removeEventListener("finops:notification-prefs-changed", onSync);
  }, [userId]);

  const updatePreference = useCallback(
    <K extends keyof NotificationPreferences>(key: K, value: NotificationPreferences[K]) => {
      setPreferences((current) => {
        const next = { ...current, [key]: value };
        saveNotificationPreferences(next, userId);
        return next;
      });
    },
    [userId]
  );

  return {
    preferences,
    updatePreference,
  };
}
