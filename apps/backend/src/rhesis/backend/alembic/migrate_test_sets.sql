INSERT INTO public.test_test_set (test_id, test_set_id)
SELECT t.id AS test_id, pts.test_set_id
FROM public.prompt_test_set pts
JOIN public.test t
  ON t.prompt_id = pts.prompt_id
LEFT JOIN public.test_test_set existing
  ON existing.test_id = t.id AND existing.test_set_id = pts.test_set_id
WHERE existing.test_id IS NULL; -- Only insert if not already present