import type { Stage } from "./api";

export function stageForBirthDate(
  value: string,
  reference = new Date(),
): Stage | null {
  if (!value) return null;
  const birth = new Date(`${value}T00:00:00`);
  if (Number.isNaN(birth.getTime()) || birth > reference) return null;

  const schoolYear =
    reference.getMonth() >= 2 ? reference.getFullYear() : reference.getFullYear() - 1;
  const grade = schoolYear - (birth.getFullYear() + 6);
  if (grade >= 1 && grade <= 6) return "elementary";
  if (grade >= 7 && grade <= 9) return "middle";
  if (grade >= 10 && grade <= 12) return "high";

  let months =
    (reference.getFullYear() - birth.getFullYear()) * 12
    + reference.getMonth()
    - birth.getMonth();
  if (reference.getDate() < birth.getDate()) months -= 1;
  if (months <= 35) return "infant_0_2";
  if (months <= 83) return "preschool_3_5";
  return null;
}
