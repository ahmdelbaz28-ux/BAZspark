import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import {
  BookOpenText,
  ChevronRight,
  Copy,
  ExternalLink,
  X,
  Search,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useSmartHelp } from '@/hooks/useSmartHelp';
import {
  getFallbackHelpTopic,
  getFirstTopicForContext,
  getHelpCategories,
  getHelpTopic,
  getRelatedTopics,
  searchHelpTopics,
} from '@/help/contextRegistry';
import type { HelpCategory, HelpTopic } from '@/help/types';

export function SmartHelpDrawer() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const {
    isOpen,
    isSearchOpen,
    activeContextId,
    selectedTopicId,
    query,
    category,
    closeHelp,
    selectTopic,
    setQuery,
    setCategory,
    clearFilters,
  } = useSmartHelp();

  const [copiedTopicId, setCopiedTopicId] = useState<string | null>(null);
  const isRtl = document.documentElement.dir === 'rtl' || i18n.language.startsWith('ar');
  const categories = useMemo(() => getHelpCategories(), []);

  const results = searchHelpTopics(query, category, i18n.language);
  const activeContextTopic = getFirstTopicForContext(activeContextId);
  const selectedTopic = selectedTopicId
    ? getHelpTopic(selectedTopicId)
    : activeContextTopic ?? results[0]?.topic ?? null;
  const fallbackTopic = results.length === 0 && query.trim() ? getFallbackHelpTopic(query) : null;
  const displayedTopic: HelpTopic | null = selectedTopic ?? fallbackTopic;
  const relatedTopics = displayedTopic ? getRelatedTopics(displayedTopic) : [];

  useEffect(() => {
    if (!isOpen) return undefined;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        closeHelp();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, closeHelp]);

  useEffect(() => {
    if (!isOpen) return;
    setCopiedTopicId(null);
  }, [isOpen, displayedTopic?.id]);

  const handleCopyTopicId = async () => {
    if (!displayedTopic) return;

    try {
      await navigator.clipboard.writeText(displayedTopic.id);
      setCopiedTopicId(displayedTopic.id);
    } catch {
      setCopiedTopicId(null);
    }
  };

  const handleNavigate = () => {
    if (!displayedTopic?.navigateTo) return;
    navigate(displayedTopic.navigateTo);
    closeHelp();
  };

  const panelClasses = isRtl
    ? 'left-0 border-r border-slate-800'
    : 'right-0 border-l border-slate-800';

  return (
    <div
      className={`fixed inset-0 z-[120] ${isOpen ? 'pointer-events-auto' : 'pointer-events-none'}`}
      dir={isRtl ? 'rtl' : 'ltr'}
      aria-hidden={!isOpen}
    >
      <div
        className={`absolute inset-0 bg-black/60 transition-opacity duration-300 ${isOpen ? 'opacity-100' : 'opacity-0'}`}
        onClick={closeHelp}
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-label={t('help.title')}
        className={`fixed top-0 bottom-0 z-10 flex w-[min(58rem,94vw)] flex-col bg-slate-950 shadow-2xl transition-transform duration-300 ${panelClasses} ${isOpen ? 'translate-x-0' : isRtl ? '-translate-x-full' : 'translate-x-full'}`}
      >
        <header className="flex shrink-0 items-center gap-3 border-b border-slate-800 p-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-red-500/10 text-red-400">
            <BookOpenText className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-base font-semibold text-slate-100">{t('help.title')}</h2>
            <p className="text-xs text-slate-400">
              {isSearchOpen ? t('help.searchMode') : t('help.browseMode')}
            </p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="text-slate-400 hover:bg-slate-800 hover:text-slate-100"
            onClick={closeHelp}
            aria-label={t('common.close')}
          >
            <X className="h-4 w-4" />
          </Button>
        </header>

        <div className="space-y-3 border-b border-slate-800 p-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500 rtl:left-auto rtl:right-3" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t('help.searchPlaceholder')}
              className="bg-slate-900 border-slate-700 pr-10 text-slate-100 placeholder:text-slate-500 focus-visible:ring-red-500/40 rtl:pl-10 rtl:pr-3"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant={category === 'all' ? 'secondary' : 'outline'}
              size="sm"
              className="h-7 border-slate-700 text-xs"
              onClick={() => setCategory('all')}
            >
              {t('help.allCategories')}
            </Button>
            {categories.map((categoryName) => (
              <Button
                key={categoryName}
                type="button"
                variant={category === categoryName ? 'secondary' : 'outline'}
                size="sm"
                className="h-7 border-slate-700 text-xs"
                onClick={() => setCategory(categoryName)}
              >
                {getCategoryLabel(categoryName, i18n.language)}
              </Button>
            ))}
          </div>

          {(query || category !== 'all') && (
            <button
              type="button"
              className="text-xs text-red-300 hover:text-red-200"
              onClick={clearFilters}
            >
              {t('help.clearFilters')}
            </button>
          )}
        </div>

        <div className="min-h-0 flex-1 grid grid-cols-[18rem_minmax(0,1fr)]">
          <nav className="min-h-0 overflow-y-auto border-e border-slate-800 p-3 rtl:border-e-0 rtl:border-s border-slate-800">
            <div className="mb-3 flex items-center justify-between px-2">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
                {results.length} {t('help.results')}
              </span>
              {activeContextId && (
                <span className="truncate text-xs text-slate-500" title={activeContextId}>
                  {activeContextId}
                </span>
              )}
            </div>

            {results.length === 0 ? (
              <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-sm text-amber-200">
                <AlertTriangle className="mb-2 h-4 w-4" />
                {t('help.noExactResults')}
              </div>
            ) : (
              <div className="space-y-2">
                {results.map(({ topic, matchedKeywords }) => (
                  <button
                    key={topic.id}
                    type="button"
                    className={`w-full rounded-xl border p-3 text-left transition-colors ${
                      displayedTopic?.id === topic.id
                        ? 'border-red-500/60 bg-red-500/10'
                        : 'border-slate-800 bg-slate-900/60 hover:border-slate-600 hover:bg-slate-900'
                    }`}
                    onClick={() => selectTopic(topic.id)}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-medium text-slate-100">
                        {i18n.language.startsWith('ar') ? topic.titleAr : topic.titleEn}
                      </span>
                      <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-slate-500 rtl:rotate-180" />
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs text-slate-400">
                      {i18n.language.startsWith('ar') ? topic.descriptionAr : topic.descriptionEn}
                    </p>
                    {matchedKeywords.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {matchedKeywords.slice(0, 3).map((keyword) => (
                          <span
                            key={keyword}
                            className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300"
                          >
                            {keyword}
                          </span>
                        ))}
                      </div>
                    )}
                  </button>
                ))}
              </div>
            )}
          </nav>

          <section className="min-h-0 overflow-y-auto p-5">
            {displayedTopic ? (
              <article className="space-y-5">
                <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-red-500/10 px-2.5 py-1 text-xs font-medium text-red-300">
                          {getCategoryLabel(displayedTopic.category, i18n.language)}
                        </span>
                        {displayedTopic.navigateTo && (
                          <span className="rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-300">
                            {t('help.navigationAvailable')}
                          </span>
                        )}
                      </div>
                      <h3 className="text-xl font-semibold text-slate-100">
                        {i18n.language.startsWith('ar') ? displayedTopic.titleAr : displayedTopic.titleEn}
                      </h3>
                      <p className="mt-2 text-sm leading-6 text-slate-300">
                        {i18n.language.startsWith('ar') ? displayedTopic.descriptionAr : displayedTopic.descriptionEn}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-5">
                  <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-100">
                    <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                    {t('help.steps')}
                  </h4>
                  <ol className="space-y-3">
                    {(i18n.language.startsWith('ar') ? displayedTopic.stepsAr : displayedTopic.stepsEn).map((step, index) => (
                      <li key={step} className="flex gap-3 text-sm text-slate-300">
                        <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-800 text-xs font-semibold text-red-300">
                          {index + 1}
                        </span>
                        <span>{step}</span>
                      </li>
                    ))}
                  </ol>
                </div>

                {displayedTopic.warningsEn.length > 0 && (
                  <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-5">
                    <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-amber-100">
                      <AlertTriangle className="h-4 w-4" />
                      {t('help.warnings')}
                    </h4>
                    <ul className="space-y-2 text-sm text-amber-100">
                      {(i18n.language.startsWith('ar') ? displayedTopic.warningsAr : displayedTopic.warningsEn).map((warning) => (
                        <li key={warning} className="flex gap-2">
                          <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 rtl:rotate-180" />
                          <span>{warning}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {relatedTopics.length > 0 && (
                  <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-5">
                    <h4 className="mb-3 text-sm font-semibold text-slate-100">{t('help.relatedTopics')}</h4>
                    <div className="flex flex-wrap gap-2">
                      {relatedTopics.map((topic) => (
                        <button
                          key={topic.id}
                          type="button"
                          className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-left text-xs text-slate-300 hover:border-red-500/50 hover:text-slate-100"
                          onClick={() => selectTopic(topic.id)}
                        >
                          {i18n.language.startsWith('ar') ? topic.titleAr : topic.titleEn}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <div className="flex flex-wrap gap-2">
                  {displayedTopic.navigateTo && (
                    <Button
                      type="button"
                      className="bg-red-600 text-white hover:bg-red-700"
                      onClick={handleNavigate}
                    >
                      <ExternalLink className="h-4 w-4" />
                      {t('help.openPage')}
                    </Button>
                  )}
                  <Button
                    type="button"
                    variant="outline"
                    className="border-slate-700 text-slate-300 hover:bg-slate-800"
                    onClick={handleCopyTopicId}
                  >
                    <Copy className="h-4 w-4" />
                    {copiedTopicId === displayedTopic.id ? t('help.copied') : t('help.copyTopicId')}
                  </Button>
                </div>
              </article>
            ) : (
              <div className="flex h-full flex-col items-center justify-center text-center text-slate-400">
                <BookOpenText className="mb-3 h-10 w-10 text-slate-600" />
                <p className="text-sm">{t('help.emptyState')}</p>
              </div>
            )}
          </section>
        </div>
      </aside>
    </div>
  );
}

function getCategoryLabel(category: HelpCategory, language: string): string {
  const labels: Record<HelpCategory, { en: string; ar: string }> = {
    dashboard: { en: 'Dashboard', ar: 'لوحة التحكم' },
    projects: { en: 'Projects', ar: 'المشاريع' },
    engineering: { en: 'Engineering', ar: 'الهندسة' },
    'fire-alarm': { en: 'Fire Alarm', ar: 'الإنذار' },
    reports: { en: 'Reports', ar: 'التقارير' },
    'digital-twin': { en: 'Digital Twin', ar: 'التوأم الرقمي' },
    elements: { en: 'Elements', ar: 'العناصر' },
    connections: { en: 'Connections', ar: 'الاتصالات' },
    conflicts: { en: 'Conflicts', ar: 'التعارضات' },
    settings: { en: 'Settings', ar: 'الإعدادات' },
    troubleshooting: { en: 'Troubleshooting', ar: 'استكشاف الأخطاء' },
    general: { en: 'General', ar: 'عام' },
  };

  const label = labels[category];
  return language.startsWith('ar') ? label.ar : label.en;
}
