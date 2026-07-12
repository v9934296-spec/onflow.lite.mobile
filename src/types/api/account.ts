export type ConsentStatus = {
  granted: boolean;
  granted_at: string | null;
  copy_version: string | null;
  source: string | null;
};

export type AccountMe = {
  user_id: string;
  email: string;
  tier: string;
  profile_image_url: string | null;
  theme_preference?: "system" | "light" | "dark";
  consent: ConsentStatus;
  bonus_analyses_remaining?: number | null;
  monthly_free_remaining?: number | null;
};

export type AuthSignInResult = {
  session: {
    token: string;
    userId: string;
    email: string;
  };
  isNewUser?: boolean;
  bonusAnalysesRemaining?: number;
};
