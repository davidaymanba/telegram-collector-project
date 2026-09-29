import { Link } from "react-router-dom";
import { Compass } from "lucide-react";
import { useI18n } from "@/i18n";
import { EmptyState } from "@/components/States";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  const { t } = useI18n();
  return (
    <EmptyState
      icon={Compass}
      title={t("errors.notFound")}
      description={t("errors.notFoundHint")}
      action={
        <Button asChild variant="outline">
          <Link to="/">{t("errors.home")}</Link>
        </Button>
      }
    />
  );
}
