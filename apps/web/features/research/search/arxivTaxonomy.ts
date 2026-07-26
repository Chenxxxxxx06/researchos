/**
 * Curated arXiv category taxonomy — a checked-in constant (no network).
 *
 * `id` values are arXiv-style slugs that satisfy the backend `CATEGORY_RE`
 * (`^[a-z-]+(\.[A-Za-z-]+)?$`). `label` is a human gloss shown next to the id;
 * `group` buckets the picker. Labels are field names (technical identifiers),
 * intentionally not routed through i18n.
 */
export interface ArxivCategory {
  id: string;
  label: string;
  group: string;
}

export const GROUP_COMPUTER_SCIENCE = 'Computer Science';
export const GROUP_STATISTICS = 'Statistics';
export const GROUP_MATHEMATICS = 'Mathematics';
export const GROUP_EE = 'Electrical Engineering';
export const GROUP_PHYSICS = 'Physics & Other';

export const ARXIV_CATEGORIES: ArxivCategory[] = [
  // Computer Science
  { id: 'cs.LG', label: 'Machine Learning', group: GROUP_COMPUTER_SCIENCE },
  { id: 'cs.AI', label: 'Artificial Intelligence', group: GROUP_COMPUTER_SCIENCE },
  { id: 'cs.CL', label: 'Computation and Language', group: GROUP_COMPUTER_SCIENCE },
  { id: 'cs.CV', label: 'Computer Vision', group: GROUP_COMPUTER_SCIENCE },
  { id: 'cs.RO', label: 'Robotics', group: GROUP_COMPUTER_SCIENCE },
  { id: 'cs.NE', label: 'Neural & Evolutionary Computing', group: GROUP_COMPUTER_SCIENCE },
  { id: 'cs.IR', label: 'Information Retrieval', group: GROUP_COMPUTER_SCIENCE },
  { id: 'cs.CR', label: 'Cryptography & Security', group: GROUP_COMPUTER_SCIENCE },
  { id: 'cs.DC', label: 'Distributed & Cluster Computing', group: GROUP_COMPUTER_SCIENCE },
  { id: 'cs.DS', label: 'Data Structures & Algorithms', group: GROUP_COMPUTER_SCIENCE },
  { id: 'cs.HC', label: 'Human-Computer Interaction', group: GROUP_COMPUTER_SCIENCE },
  { id: 'cs.SE', label: 'Software Engineering', group: GROUP_COMPUTER_SCIENCE },
  { id: 'cs.SD', label: 'Sound', group: GROUP_COMPUTER_SCIENCE },
  { id: 'cs.MA', label: 'Multiagent Systems', group: GROUP_COMPUTER_SCIENCE },
  { id: 'cs.GT', label: 'Computer Science & Game Theory', group: GROUP_COMPUTER_SCIENCE },
  { id: 'cs.DB', label: 'Databases', group: GROUP_COMPUTER_SCIENCE },

  // Statistics
  { id: 'stat.ML', label: 'Machine Learning', group: GROUP_STATISTICS },
  { id: 'stat.ME', label: 'Methodology', group: GROUP_STATISTICS },
  { id: 'stat.TH', label: 'Statistics Theory', group: GROUP_STATISTICS },
  { id: 'stat.AP', label: 'Applications', group: GROUP_STATISTICS },
  { id: 'stat.CO', label: 'Computation', group: GROUP_STATISTICS },

  // Mathematics
  { id: 'math.OC', label: 'Optimization & Control', group: GROUP_MATHEMATICS },
  { id: 'math.ST', label: 'Statistics Theory', group: GROUP_MATHEMATICS },
  { id: 'math.PR', label: 'Probability', group: GROUP_MATHEMATICS },
  { id: 'math.NA', label: 'Numerical Analysis', group: GROUP_MATHEMATICS },
  { id: 'math.IT', label: 'Information Theory', group: GROUP_MATHEMATICS },
  { id: 'math.DS', label: 'Dynamical Systems', group: GROUP_MATHEMATICS },

  // Electrical Engineering & Systems Science
  { id: 'eess.SP', label: 'Signal Processing', group: GROUP_EE },
  { id: 'eess.IV', label: 'Image & Video Processing', group: GROUP_EE },
  { id: 'eess.AS', label: 'Audio & Speech Processing', group: GROUP_EE },
  { id: 'eess.SY', label: 'Systems & Control', group: GROUP_EE },

  // Physics & Other
  { id: 'quant-ph', label: 'Quantum Physics', group: GROUP_PHYSICS },
  { id: 'astro-ph.GA', label: 'Astrophysics of Galaxies', group: GROUP_PHYSICS },
  { id: 'cond-mat.dis-nn', label: 'Disordered Systems & Neural Networks', group: GROUP_PHYSICS },
  { id: 'physics.comp-ph', label: 'Computational Physics', group: GROUP_PHYSICS },
  { id: 'physics.data-an', label: 'Data Analysis & Statistics', group: GROUP_PHYSICS },
  { id: 'q-bio.NC', label: 'Neurons & Cognition', group: GROUP_PHYSICS },
];

export const GROUP_ORDER: string[] = [
  GROUP_COMPUTER_SCIENCE,
  GROUP_STATISTICS,
  GROUP_MATHEMATICS,
  GROUP_EE,
  GROUP_PHYSICS,
];

export interface CategoryGroup {
  group: string;
  items: ArxivCategory[];
}

/** Group the flat taxonomy into ordered buckets for the picker UI. */
export function groupCategories(): CategoryGroup[] {
  return GROUP_ORDER.map((group) => ({
    group,
    items: ARXIV_CATEGORIES.filter((c) => c.group === group),
  })).filter((g) => g.items.length > 0);
}

const LABELS: Record<string, string> = Object.fromEntries(
  ARXIV_CATEGORIES.map((c) => [c.id, c.label]),
);

/** Human label for a category id, falling back to the id itself. */
export function categoryLabel(id: string): string {
  return LABELS[id] ?? id;
}
