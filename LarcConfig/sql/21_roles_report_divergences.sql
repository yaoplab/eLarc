-- Rapport (lecture seule) : divergences restantes après la phase A.
SELECT a.id, a.last_name,
       a.type_director AS aec_director, t.is_director, t.is_adm
FROM larcauth_aecuser a JOIN larcauth_teachadm t ON t.aecuser_ptr_id = a.id
WHERE a.type_director IS DISTINCT FROM t.is_adm
ORDER BY a.id;
