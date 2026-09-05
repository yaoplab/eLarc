"""Seed: parents realistes, liens eleve-parent, paiements aleatoires."""
import random
import sys, os

_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)
sys.path.insert(0, os.path.join(_root, "LarcCommon"))

from larccommon.database import db

if not db.connect_intranet():
    print("Intranet non disponible")
    sys.exit(1)

cur = db.server_conn.cursor()

# ── 1. Noms factices réalistes ──
first_names_m = ["Koffi", "Yao", "Kouame", "Amani", "Konan", "N'Guessan", "Traore",
                  "Diawara", "Keita", "Coulibaly", "Bamba", "Soro", "Ouattara", "Diallo",
                  "Konate", "Toure", "Sangare", "Fofana", "Doumbia", "Sissoko"]
first_names_f = ["Aya", "Adjoua", "Amoin", "Akissi", "N'Dri", "Bakayoko", "Cisse",
                  "Camara", "Diomande", "Ahou", "Ehui", "Fanta", "Kone", "Maiga",
                  "Tano", "Yeo", "Kone", "Sako", "Soumahoro", "Kouassi"]
last_names = ["Koffi", "Konan", "Yao", "Traore", "Ouattara", "Kouame", "Diallo",
              "Bamba", "Coulibaly", "Soro", "N'Guessan", "Toure", "Fofana",
              "Kone", "Diawara", "Sangare", "Camara", "Cisse", "Keita", "Doumbia"]

random.seed(2026)
cur.execute("SELECT aecuser_ptr_id FROM larcauth_parent WHERE enabled = true ORDER BY aecuser_ptr_id")
parents = [(r[0],) for r in cur.fetchall()]  # (aecuser_ptr_id,)
print(f"Parents a renommer: {len(parents)}")

for (aid,) in parents:
    fn = random.choice(first_names_m if random.random() > 0.5 else first_names_f)
    ln = random.choice(last_names)
    tel = f"07{random.randint(10000000,99999999)}"
    cur.execute("""
        UPDATE larcauth_aecuser SET first_name = %s, last_name = %s,
        tel_smartphone_1 = %s, email = %s, emailperso = %s
        WHERE id = %s
    """, (fn, ln, tel, f"{fn.lower()}.{ln.lower()}@email.ci",
          f"{fn.lower()}.{ln.lower()}@gmail.com", aid))
print("Noms parents mis a jour")

# ── 2. Liens eleve-parent ──
cur.execute("""SELECT a.id, a.first_name, a.last_name, s.s_classroom_id
    FROM larcauth_aecuser a
    JOIN larcauth_student s ON s.aecuser_ptr_id = a.id
    WHERE s.enabled = true ORDER BY a.id""")
students = cur.fetchall()
print(f"Eleves actifs: {len(students)}")

cur.execute("DELETE FROM larcauth_student_parent")
natures = ["pere", "mere", "tuteur", "tutrice"]

for sid, fn, ln, cid in students:
    # 1 ou 2 parents par eleve
    np = random.choices([1, 2], weights=[0.6, 0.4])[0]
    assigned = set()
    for _ignored in range(np):
        (aid,) = random.choice(parents)
        if aid in assigned:
            continue
        assigned.add(aid)
        nature = random.choice(natures)
        cur.execute("""
            INSERT INTO larcauth_student_parent (student_id, parent_id, nature, is_emergency, is_authorized)
            VALUES (%s, %s, %s, %s, TRUE)
            ON CONFLICT DO NOTHING
        """, (sid, aid, nature, random.random() < 0.3))
print("Liens eleve-parent crees")

# ── 3. Plans de paiement ──
COLLEGE = 2500000
LYCEE = 3000000
cur.execute("DELETE FROM compta_payment_schedule")
cur.execute("DELETE FROM compta_payment")

for sid, fn, ln, cid in students:
    cur.execute("""SELECT l.fk_program_id FROM larcauth_classroom c
        JOIN larcauth_level l ON l.id = c.fk_level_id WHERE c.id = %s""", (cid,))
    pid = cur.fetchone()[0]
    fee = LYCEE if pid in (13, 23) else COLLEGE
    mode = random.choice(["mensuel", "trimestriel", "annuel"])
    monthly = fee // 10 if mode == "mensuel" else None
    term = fee // 3 if mode == "trimestriel" else None

    cur.execute("""INSERT INTO compta_payment_schedule
        (student_id, academic_year, total_due, payment_mode, monthly_amount, term_amount)
        VALUES (%s, '2026-2027', %s, %s, %s, %s)
        ON CONFLICT DO NOTHING""",
        (sid, fee, mode, monthly, term))

    # ── 4. Paiements aleatoires ──
    paid_total = 0
    months = ["2026-09-01", "2026-10-01", "2026-11-01", "2026-12-01",
              "2027-01-05", "2027-02-01", "2027-03-01", "2027-04-01",
              "2027-05-01", "2027-06-01"]
    # Decide payment status: paid=60%, partial=25%, unpaid=15%
    status = random.choices(["paid", "partial", "unpaid"], weights=[0.60, 0.25, 0.15])[0]
    if status == "paid":
        cur.execute("""INSERT INTO compta_payment (student_id, amount, payment_date, payment_method, reference)
            VALUES (%s, %s, '2026-09-01', 'virement', 'PAID-FULL')""", (sid, fee))
    elif status == "partial":
        n_payments = random.randint(1, 4)
        for _ignored in range(n_payments):
            amt = random.randint(fee // 20, fee // 4)
            paid_total += amt
            if paid_total > fee:
                amt -= (paid_total - fee)
                paid_total = fee
            d = random.choice(months)
            cur.execute("""INSERT INTO compta_payment (student_id, amount, payment_date, payment_method)
                VALUES (%s, %s, %s, %s)""", (sid, amt, d, random.choice(["especes", "virement", "mobile_money"])))
    # else unpaid: no payments

print("Plans et paiements generes")

# ── 5. Stats ──
cur.execute("SELECT COUNT(*) FROM larcauth_student_parent")
print(f"Liens eleve-parent: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM compta_payment_schedule")
print(f"Plans de paiement: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM compta_payment")
c, s = cur.fetchone()
print(f"Paiements: {c}, total encaisse: {s:,} FCFA")
cur.execute("""SELECT payment_mode, COUNT(*) FROM compta_payment_schedule
    GROUP BY payment_mode ORDER BY COUNT(*) DESC""")
print("Modes de paiement:")
for r in cur.fetchall(): print(f"  {r[0]}: {r[1]}")

db.disconnect_all()
print("Termine")
