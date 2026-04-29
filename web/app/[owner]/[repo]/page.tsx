import { fetchGraph } from "@/lib/api";
import RepoExplorer from "./RepoExplorer";
import { notFound } from "next/navigation";

interface Props {
  params: Promise<{ owner: string; repo: string }>;
}

export default async function RepoPage({ params }: Props) {
  const { owner, repo } = await params;

  let data;
  try {
    data = await fetchGraph(owner, repo);
  } catch (e: any) {
    if (e.message === "Repo not found") notFound();
    throw e;
  }

  return <RepoExplorer data={data} />;
}
