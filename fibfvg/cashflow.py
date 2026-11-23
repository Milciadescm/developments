"""Personal cash flow Dec 2026 -> Dec 2028: salary, fund interest, prop withdrawals, apartment and GLE 63 S.

Inputs (from the owner): salary $2,000/month, fixed expenses $1,100/month. Inheritance RD$3,000,000 into a fund at
11% a year, paid monthly into a separate account; arrives July 2027 (alternative: December 2027). RD$63 per US$ assumed.
Dominican withholding tax on interest for individuals: 10% (check with your bank).
Prop accounts (2027 plan, 10 accounts): 2 bought 1 Dec 2026, +1 in March, April, May 2027 from personal funds,
+5 on 1 June 2027 from the May withdrawal. Withdrawals (median of 2,000 paths): 26 May 2027 $18,446; December 2027
$40,261; from January 2028 the 10 accounts are assumed to pay their 2024-26 average, about $5,100 a month
(real months are uneven: many pay $0, a few pay a lot).
Apartment: down payment $7,900 (fastest) to $35,000 (safest), then $400 a month.
GLE 63 S: cash $60,000-$70,000 (planned at $65,000); financed: 20% down ($13,000), $52,000 at 11% for 60 months
= about $1,131 a month, total about $80,900.
Rules for every approach: an emergency fund of 6 months of fixed costs first; the inheritance stays in the fund (only
its interest is spent); 25% of every prop withdrawal goes to Bitcoin / investment before anything is bought.
    python -m fibfvg.cashflow -> results/cashflow.json
"""
import json

import pandas as pd

RD_PER_USD = 63.0
INHERIT_USD = 3_000_000 / RD_PER_USD
FUND_RATE = 0.11
WHT = 0.10
SALARY, FIXED = 2_000.0, 1_100.0
FEE = 740.0
MONTHS = pd.date_range("2026-12-01", "2028-12-01", freq="MS")


def loan_payment(principal, rate, n):
    r = rate / 12
    return principal * r / (1 - (1 + r) ** -n)


CAR_CASH = 65_000.0
CAR_DOWN = 13_000.0
CAR_PMT = loan_payment(52_000, 0.11, 60)


def prop_income(m, trading=True):
    if not trading:
        return 0.0
    if m == pd.Timestamp("2027-05-01"):
        return 18_446.0
    if m == pd.Timestamp("2027-12-01"):
        return 40_261.0
    if m >= pd.Timestamp("2028-01-01"):
        return 5_100.0
    return 0.0


def fees(m):
    k = {"2026-12-01": 2, "2027-03-01": 1, "2027-04-01": 1, "2027-05-01": 1, "2027-06-01": 5}.get(str(m.date()), 0)
    return k * FEE


def run(approach, inherit_month="2027-07-01"):
    """approach: safest / fastest / slowest"""
    trading = approach != "slowest"
    apt_dp = 35_000.0 if approach == "safest" else 7_900.0
    wallet, invest, fund = 0.0, 0.0, 0.0
    emergency = 6 * FIXED
    apt = car = False; car_loan_left = 0
    rows = []
    for m in MONTHS:
        ev = []
        inc_sal = SALARY
        if m == pd.Timestamp(inherit_month):
            fund = INHERIT_USD; ev.append(f"inheritance ${INHERIT_USD:,.0f} into the 11% fund")
        inc_int = fund * FUND_RATE / 12 * (1 - WHT) if m > pd.Timestamp(inherit_month) else 0.0
        inc_prop = prop_income(m, trading)
        to_inv = 0.25 * inc_prop
        out_fix = FIXED
        out_fee = fees(m) if trading else 0.0
        out_apt = 400.0 if apt else 0.0
        out_car = CAR_PMT if car_loan_left > 0 else 0.0
        if car_loan_left > 0:
            car_loan_left -= 1
        wallet += inc_sal + inc_int + inc_prop - to_inv - out_fix - out_fee - out_apt - out_car
        invest += to_inv
        buys = 0.0
        # monthly cost after the purchases being considered, must stay below salary + interest + safe prop income
        if not apt and wallet >= emergency + apt_dp:
            wallet -= apt_dp; buys += apt_dp; apt = True; ev.append(f"apartment down payment ${apt_dp:,.0f}; $400 a month from next month")
        if apt and not car:
            if approach == "fastest" and wallet >= emergency + CAR_DOWN and m >= pd.Timestamp("2027-12-01"):
                wallet -= CAR_DOWN; buys += CAR_DOWN; car = True; car_loan_left = 60
                ev.append(f"GLE 63 S financed: ${CAR_DOWN:,.0f} down, ${CAR_PMT:,.0f} a month for 60 months")
            elif approach in ("safest", "slowest") and wallet >= 2 * emergency + CAR_CASH:
                wallet -= CAR_CASH; buys += CAR_CASH; car = True; ev.append(f"GLE 63 S bought in cash ${CAR_CASH:,.0f}")
        rows.append(dict(month=m.strftime("%b %Y"), salary=round(inc_sal), fund_interest=round(inc_int), prop=round(inc_prop),
                         income=round(inc_sal + inc_int + inc_prop), fixed=round(out_fix), prop_fees=round(out_fee), apartment=round(out_apt),
                         car=round(out_car), purchases=round(buys), to_investments=round(to_inv), wallet=round(wallet),
                         investments=round(invest), fund=round(fund), events="; ".join(ev)))
    return rows


def main():
    out = dict(assumptions=dict(inheritance_usd=round(INHERIT_USD), fund_interest_month_gross=round(INHERIT_USD * FUND_RATE / 12),
                                fund_interest_month_net=round(INHERIT_USD * FUND_RATE / 12 * (1 - WHT)), car_payment=round(CAR_PMT)))
    print(out["assumptions"])
    for ap in ("safest", "fastest", "slowest"):
        for im in ("2027-07-01", "2027-12-01"):
            rows = run(ap, im)
            out[f"{ap} | inheritance {im[:7]}"] = rows
            evs = [(r["month"], r["events"]) for r in rows if r["events"]]
            print(f"\n{ap.upper()} (inheritance {im[:7]}): end wallet ${rows[-1]['wallet']:,} investments ${rows[-1]['investments']:,}")
            for e in evs:
                print("   ", e)
    for r in out["safest | inheritance 2027-07"]:
        print(r)
    json.dump(out, open("results/cashflow.json", "w"), indent=1)


if __name__ == "__main__":
    main()
