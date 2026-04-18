import { CalendarIcon, Clock3 } from "lucide-react"
import { format } from "date-fns"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"

function pad(value: number) {
  return value.toString().padStart(2, "0")
}

function parseLocalDraft(value: string): Date | null {
  if (!value) return null
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/)
  if (!match) return null
  const [, year, month, day, hour, minute] = match
  return new Date(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    0,
    0
  )
}

function formatLocalDraft(date: Date): string {
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
  ].join("-") + `T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function getTimePart(value: string): string {
  const parsed = parseLocalDraft(value)
  if (!parsed) return "09:00"
  return `${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`
}

interface DateTimePickerFieldProps {
  value: string
  onChange: (nextValue: string) => void
  placeholder?: string
  disabled?: boolean
  className?: string
}

export function DateTimePickerField({
  value,
  onChange,
  placeholder = "Pick a date",
  disabled = false,
  className,
}: DateTimePickerFieldProps) {
  const selectedDate = parseLocalDraft(value)

  function updateDate(nextDate: Date | undefined) {
    if (!nextDate) {
      onChange("")
      return
    }
    const [hours, minutes] = getTimePart(value).split(":").map(Number)
    const merged = new Date(nextDate)
    merged.setHours(hours, minutes, 0, 0)
    onChange(formatLocalDraft(merged))
  }

  function updateTime(nextTime: string) {
    if (!nextTime) {
      onChange("")
      return
    }
    const [hours, minutes] = nextTime.split(":").map(Number)
    const base = selectedDate ? new Date(selectedDate) : new Date()
    base.setHours(hours, minutes, 0, 0)
    onChange(formatLocalDraft(base))
  }

  return (
    <div className={cn("grid gap-2", className)}>
      <Popover>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            disabled={disabled}
            className={cn(
              "w-full justify-start rounded-xl text-left font-normal",
              !selectedDate && "text-muted-foreground"
            )}
          >
            <CalendarIcon className="mr-2 h-4 w-4" />
            {selectedDate ? format(selectedDate, "PPP") : placeholder}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="single"
            selected={selectedDate ?? undefined}
            onSelect={updateDate}
            initialFocus
          />
        </PopoverContent>
      </Popover>

      <div className="relative">
        <Clock3 className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="time"
          step={60}
          disabled={disabled}
          value={selectedDate ? getTimePart(value) : ""}
          onChange={(event) => updateTime(event.target.value)}
          className="rounded-xl pl-10"
        />
      </div>
    </div>
  )
}
