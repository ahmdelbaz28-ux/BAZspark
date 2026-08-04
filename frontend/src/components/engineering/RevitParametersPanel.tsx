import { useState, useEffect } from "react";
import { Loader2, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface RevitParametersPanelProps {
        elementId: string;
}

export function RevitParametersPanel({ elementId }: RevitParametersPanelProps) {
        const [parameters, setParameters] = useState<Record<string, string>>({});
        const [loading, setLoading] = useState(false);
        const [saving, setSaving] = useState(false);
        const [isEditing, setIsEditing] = useState(false);

        const loadParameters = async () => {
                setLoading(true);
                try {
                        const apiUrl = import.meta.env.VITE_API_URL || "/api/v1";
                        const res = await fetch(`${apiUrl}/elements/${elementId}/parameters`, {
                                credentials: "same-origin",
                        });
                        if (res.ok) {
                                const data = await res.json();
                                setParameters(data.parameters || data || {});
                        } else if (res.status !== 404) {
                                throw new Error("Failed to load parameters");
                        }
                } catch (error) {
                        toast.error(`Error loading parameters: ${(error as Error).message}`);
                } finally {
                        setLoading(false);
                }
        };

        useEffect(() => {
                loadParameters();
        }, [elementId]);

        const handleSave = async () => {
                setSaving(true);
                try {
                        const apiUrl = import.meta.env.VITE_API_URL || "/api/v1";
                        const res = await fetch(`${apiUrl}/elements/${elementId}/parameters`, {
                                method: "PUT",
                                headers: {
                                        "Content-Type": "application/json",
                                },
                                body: JSON.stringify(parameters),
                                credentials: "same-origin",
                        });
                        if (!res.ok) throw new Error("Failed to save parameters");
                        toast.success("Parameters saved successfully");
                        setIsEditing(false);
                } catch (error) {
                        toast.error(`Error saving parameters: ${(error as Error).message}`);
                } finally {
                        setSaving(false);
                }
        };

        const updateParam = (key: string, value: string) => {
                setParameters(prev => ({ ...prev, [key]: value }));
        };

        const deleteParam = (key: string) => {
                setParameters(prev => {
                        const next = { ...prev };
                        delete next[key];
                        return next;
                });
        };

        const addParam = () => {
                setParameters(prev => ({ ...prev, "New Parameter": "" }));
        };

        if (loading) {
                return <div className="flex items-center justify-center p-4"><Loader2 className="animate-spin h-6 w-6 text-muted-foreground" /></div>;
        }

        return (
                <div className="bg-card border border-border rounded-md p-6">
                        <div className="flex items-center justify-between mb-4">
                                <h2 className="text-lg font-semibold text-white">Revit Parameters</h2>
                                {!isEditing ? (
                                        <Button variant="outline" size="sm" onClick={() => setIsEditing(true)}>
                                                Edit Parameters
                                        </Button>
                                ) : (
                                        <div className="flex gap-2">
                                                <Button variant="ghost" size="sm" onClick={() => setIsEditing(false)}>Cancel</Button>
                                                <Button size="sm" onClick={handleSave} disabled={saving}>
                                                        {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                                        Save
                                                </Button>
                                        </div>
                                )}
                        </div>

                        {Object.keys(parameters).length === 0 && !isEditing ? (
                                <p className="text-muted-foreground text-sm">No parameters found for this element.</p>
                        ) : (
                                <div className="space-y-3">
                                        {Object.entries(parameters).map(([key, value], i) => (
                                                <div key={i} className="flex gap-2 items-center">
                                                        {isEditing ? (
                                                                <>
                                                                        <Input
                                                                                value={key}
                                                                                onChange={(e) => {
                                                                                        const newKey = e.target.value;
                                                                                        const { [key]: oldVal, ...rest } = parameters;
                                                                                        setParameters({ ...rest, [newKey]: value });
                                                                                }}
                                                                                className="flex-1 bg-card text-sm"
                                                                                placeholder="Key"
                                                                        />
                                                                        <Input
                                                                                value={value as string}
                                                                                onChange={(e) => updateParam(key, e.target.value)}
                                                                                className="flex-1 bg-card text-sm"
                                                                                placeholder="Value"
                                                                        />
                                                                        <Button variant="ghost" size="icon" onClick={() => deleteParam(key)}>
                                                                                <Trash2 className="h-4 w-4 text-danger" />
                                                                        </Button>
                                                                </>
                                                        ) : (
                                                                <div className="flex-1 grid grid-cols-2">
                                                                        <div className="text-xs text-muted-foreground">{key}</div>
                                                                        <div className="text-sm text-white">{String(value)}</div>
                                                                </div>
                                                        )}
                                                </div>
                                        ))}
                                        
                                        {isEditing && (
                                                <Button variant="outline" size="sm" className="w-full mt-2" onClick={addParam}>
                                                        <Plus className="h-4 w-4 mr-2" /> Add Parameter
                                                </Button>
                                        )}
                                </div>
                        )}
                </div>
        );
}
