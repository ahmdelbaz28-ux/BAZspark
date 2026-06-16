import { HELP_CATEGORY_LABELS, HELP_TOPICS, HELP_TOPIC_ORDER } from './helpTopics';
import type { HelpCategory, HelpSearchResult, HelpTopic, HelpTopicId } from './types';

export function getHelpTopic(topicId: HelpTopicId | string | null | undefined): HelpTopic | undefined {
  if (!topicId) return undefined;
  return HELP_TOPICS[topicId as HelpTopicId];
}

export function getHelpCategories(): HelpCategory[] {
  const categories = new Set<HelpCategory>();
  for (const topic of Object.values(HELP_TOPICS)) {
    categories.add(topic.category);
  }
  return Array.from(categories).sort((a, b) => HELP_CATEGORY_LABELS[a].en.localeCompare(HELP_CATEGORY_LABELS[b].en));
}

export function getCategoryLabel(category: HelpCategory, language: string): string {
  const labels = HELP_CATEGORY_LABELS[category] ?? HELP_CATEGORY_LABELS.general;
  return language.startsWith('ar') ? labels.ar : labels.en;
}

function normalize(value: string): string {
  return value
    .toLocaleLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^\p{L}\p{N}\s-]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function tokenize(value: string): string[] {
  const normalized = normalize(value);
  return normalized ? normalized.split(' ') : [];
}

function includesToken(haystack: string, token: string): boolean {
  const normalizedHaystack = normalize(haystack);
  return normalizedHaystack === token || normalizedHaystack.includes(token);
}

function scoreTopic(topic: HelpTopic, tokens: string[]): { score: number; matchedKeywords: string[] } {
  if (tokens.length === 0) {
    return { score: topic.category === 'troubleshooting' ? 2 : 1, matchedKeywords: [] };
  }

  let score = 0;
  const matchedKeywords = new Set<string>();

  for (const token of tokens) {
    if (normalize(topic.id) === token) {
      score += 100;
      continue;
    }

    const title = `${topic.titleEn} ${topic.titleAr}`;
    const description = `${topic.descriptionEn} ${topic.descriptionAr}`;
    const steps = [...topic.stepsEn, ...topic.stepsAr].join(' ');
    const warnings = [...topic.warningsEn, ...topic.warningsAr].join(' ');

    if (includesToken(title, token)) score += 18;
    if (includesToken(description, token)) score += 8;
    if (includesToken(topic.category, token)) score += 6;
    if (includesToken(steps, token)) score += 5;
    if (includesToken(warnings, token)) score += 3;

    for (const keyword of topic.keywords) {
      if (includesToken(keyword, token)) {
        score += 12;
        matchedKeywords.add(keyword);
      }
    }
  }

  return { score, matchedKeywords: Array.from(matchedKeywords) };
}

export function searchHelpTopics(
  query: string,
  category: HelpCategory | 'all',
  language: string,
): HelpSearchResult[] {
  const tokens = tokenize(query);
  const results: HelpSearchResult[] = [];

  for (const topicId of HELP_TOPIC_ORDER) {
    const topic = HELP_TOPICS[topicId];

    if (!topic) continue;
    if (category !== 'all' && topic.category !== category) continue;

    const { score, matchedKeywords } = scoreTopic(topic, tokens);

    if (tokens.length === 0 || score > 0) {
      const languageBoost = language.startsWith('ar') && topic.titleAr ? 1 : 0;
      results.push({
        topic,
        score: score + languageBoost,
        matchedKeywords,
      });
    }
  }

  return results.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    return a.topic.id.localeCompare(b.topic.id);
  });
}

export function getFallbackHelpTopic(query: string): HelpTopic | undefined {
  const normalized = normalize(query);

  if (normalized.includes('auth') || normalized.includes('login') || normalized.includes('token') || normalized.includes('permission')) {
    return HELP_TOPICS['troubleshooting.auth'];
  }

  if (normalized.includes('api') || normalized.includes('request') || normalized.includes('timeout') || normalized.includes('network')) {
    return HELP_TOPICS['troubleshooting.api'];
  }

  return HELP_TOPICS['troubleshooting.backend'];
}

export function getRelatedTopics(topic: HelpTopic): HelpTopic[] {
  return topic.relatedTopics
    .map((topicId) => HELP_TOPICS[topicId])
    .filter((relatedTopic): relatedTopic is HelpTopic => Boolean(relatedTopic));
}

export function getFirstTopicForContext(contextId: HelpTopicId | string | null): HelpTopic | undefined {
  const exact = getHelpTopic(contextId);
  if (exact) return exact;

  const normalizedContext = normalize(contextId ?? '');
  const orderedTopics = Object.values(HELP_TOPICS).sort((a, b) => a.id.localeCompare(b.id));

  return orderedTopics.find((topic) => {
    const searchable = normalize(`${topic.id} ${topic.titleEn} ${topic.titleAr} ${topic.keywords.join(' ')}`);
    return searchable.includes(normalizedContext);
  });
}
