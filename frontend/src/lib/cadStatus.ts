/**
 * Shared status-check helper for CAD integration pages (AutoCAD, Revit).
 *
 * Extracted to eliminate cross-file duplication between AutoCADPage.tsx and
 * RevitPage.tsx (SonarCloud CPD finding on PR #285 — both pages had identical
 * 16-line checkStatus blocks that differed only in the API call).
 *
 * The helper performs the status fetch + state updates AFTER the first await,
 * so it is safe to call from a mount effect's async IIFE without triggering
 * react-hooks/set-state-in-effect (the linter does not trace through
 * module-level functions that take setters as arguments).
 */

interface CadStatusCallbacks {
        setStatus: (s: Record<string, unknown> | null) => void;
        setConnected: (c: boolean) => void;
        setSimulationMode: (m: boolean) => void;
}

/**
 * Fetch CAD/BIM integration status and update the caller's state.
 *
 * @param getStatus - The API call that returns the status object (e.g. `autocadApi.getStatus` or `revitApi.getStatus`).
 * @param callbacks - The setState functions to call with the result.
 * @param isCancelled - Optional cancellation check (returns true if the caller has unmounted / the effect has been cleaned up).
 */
export async function checkCadStatus(
        getStatus: () => Promise<unknown>,
        callbacks: CadStatusCallbacks,
        isCancelled: () => boolean = () => false,
): Promise<void> {
        try {
                const s = await getStatus();
                if (isCancelled()) return;
                callbacks.setStatus(s as Record<string, unknown>);
                callbacks.setConnected(true);
                const sim = (s as Record<string, unknown>)?.simulation_mode;
                callbacks.setSimulationMode(Boolean(sim));
        } catch {
                if (isCancelled()) return;
                callbacks.setConnected(false);
                callbacks.setStatus(null);
                callbacks.setSimulationMode(false);
        }
}
