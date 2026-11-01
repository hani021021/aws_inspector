export type RepoImage = {
  digest: string;
  tags: string[];
  children: string[];
};

export type PlannedImage = RepoImage & { protected: boolean };

export type DeletionPlan = {
  protectedTagFound: boolean;
  images: PlannedImage[];
  first: string[];
  then: string[];
};

// Decides which images may be deleted. The image carrying a protected tag runs in
// production; manifests referenced by a protected index are protected too.
// Without any protected tag nothing is deleted, because it is unclear what runs.
export function buildDeletionPlan(images: RepoImage[], protectedTags: string[]): DeletionPlan {
  const hasProtectedTag = (image: RepoImage) => image.tags.some((t) => protectedTags.includes(t));

  const parents = new Map<string, RepoImage[]>();
  for (const image of images) {
    for (const child of image.children) {
      parents.set(child, [...(parents.get(child) ?? []), image]);
    }
  }

  const planned = images.map((image) => ({
    ...image,
    protected:
      hasProtectedTag(image) || (parents.get(image.digest) ?? []).some(hasProtectedTag),
  }));

  const protectedTagFound = images.some(hasProtectedTag);
  const deletable = protectedTagFound ? planned.filter((i) => !i.protected) : [];

  return {
    protectedTagFound,
    images: planned,
    first: deletable.filter((i) => !parents.has(i.digest)).map((i) => i.digest),
    then: deletable.filter((i) => parents.has(i.digest)).map((i) => i.digest),
  };
}
