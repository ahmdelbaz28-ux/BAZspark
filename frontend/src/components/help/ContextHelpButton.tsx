import React from 'react';
import { useTranslation } from 'react-i18next';
import { CircleHelp } from 'lucide-react';
import { Button, type ButtonProps } from '@/components/ui/button';
import { useSmartHelp } from '@/hooks/useSmartHelp';

interface ContextHelpButtonProps {
  contextId: string;
  size?: ButtonProps['size'];
  className?: string;
  variant?: ButtonProps['variant'];
}

export function ContextHelpButton({
  contextId,
  size = 'icon',
  className = '',
  variant = 'ghost',
}: ContextHelpButtonProps) {
  const { t } = useTranslation();
  const { openHelp } = useSmartHelp();

  const tooltip = t('help.contextTooltip');

  return (
    <Button
      type="button"
      variant={variant}
      size={size}
      className={className}
      title={tooltip}
      aria-label={tooltip}
      onClick={() => openHelp(contextId)}
    >
      <CircleHelp className="h-4 w-4" />
    </Button>
  );
}
