export interface CategoryOption {
  value: string;
  label: string;
}

/**
 * Presentation-only category list — must stay in sync with the backend
 * taxonomy at apps/api/src/core/category_map.py (CATEGORIES) until a
 * GET /api/v1/categories endpoint exists. Not a ranking/eligibility rule set.
 */
export const categoryOptions: CategoryOption[] = [
  { value: "food-drink", label: "Food & Drink" },
  { value: "street-food", label: "Street Food" },
  { value: "cafes", label: "Cafés" },
  { value: "culture-heritage", label: "Culture & Heritage" },
  { value: "art-galleries", label: "Art & Galleries" },
  { value: "museums", label: "Museums" },
  { value: "workshops", label: "Workshops" },
  { value: "crafts", label: "Crafts" },
  { value: "shopping-markets", label: "Shopping & Markets" },
  { value: "outdoors", label: "Outdoors" },
  { value: "adventure", label: "Adventure" },
  { value: "photography", label: "Photography" },
  { value: "family", label: "Family" },
  { value: "nightlife", label: "Nightlife" },
  { value: "music", label: "Music" },
  { value: "community", label: "Community" },
  { value: "hidden-gems", label: "Hidden Gems" },
  { value: "wellness", label: "Wellness" },
  { value: "entertainment", label: "Entertainment" },
  { value: "local-experiences", label: "Local Experiences" },
];

export const budgetOptions = [
  { value: "any", label: "Any budget" },
  { value: "low", label: "Under ₹500" },
  { value: "mid", label: "₹500 – ₹1500" },
  { value: "high", label: "₹1500+" },
];

export const durationOptions = [
  { value: "any", label: "Any duration" },
  { value: "short", label: "Under 1 hour" },
  { value: "medium", label: "1 – 3 hours" },
  { value: "long", label: "3+ hours" },
];

export const groupOptions = [
  { value: "solo", label: "Solo" },
  { value: "couple", label: "Couple" },
  { value: "friends", label: "Friends" },
  { value: "family", label: "Family" },
  { value: "business", label: "Business" },
];
