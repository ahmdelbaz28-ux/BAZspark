import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import { Check } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

const Checkbox = React.forwardRef<
        React.ElementRef<typeof CheckboxPrimitive.Root>,
        React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>
>(({ className, ...props }, ref) => (
        <CheckboxPrimitive.Root
                ref={ref}
                className={cn(
                        "grid place-content-center peer h-4 w-4 shrink-0 rounded-sm border border-primary shadow cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground transition-[background-color,border-color,box-shadow] duration-200",
                        className,
                )}
                {...props}
        >
                <CheckboxPrimitive.Indicator
                        className={cn("grid place-content-center text-current")}
                >
                        <Check aria-hidden="true" className="h-4 w-4" />
                </CheckboxPrimitive.Indicator>
        </CheckboxPrimitive.Root>
));
Checkbox.displayName = CheckboxPrimitive.Root.displayName;

export { Checkbox };
