import { useContext } from 'react';
import { SmartHelpContext } from './SmartHelpProvider';

export function useSmartHelp() {
  const context = useContext(SmartHelpContext);

  if (!context) {
    throw new Error('useSmartHelp must be used within SmartHelpProvider');
  }

  return context;
}
