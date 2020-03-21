from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import date_diff, add_months, today, getdate, add_days, flt, get_last_day, cint, get_first_day
from lear_app.lear_app.report.financial_statements import (get_period_list, get_columns, get_data, get_fiscal_year_data)
import datetime
from erpnext.accounts.utils import get_fiscal_year
from erpnext.accounts.report.budget_variance_report.budget_variance_report import get_cost_center_target_details

def execute(filters=None):

	# get from_fiscal_year
	to_fiscal_year = frappe.db.get_value("Fiscal Year", filters.fiscal_year, ["name", "year_start_date", "year_end_date"])
	try:
		from_fiscal_year = get_fiscal_year(add_days(to_fiscal_year[1], -1), company=filters.company)
	except Exception:
		frappe.throw(_('Not found Last Fiscal Year'))
	
	# set year_start_date, year_end_date
	filters.to_fiscal_year = to_fiscal_year[0]
	filters.from_fiscal_year = from_fiscal_year[0]

	fiscal_year = get_fiscal_year_data(from_fiscal_year[0], to_fiscal_year[0])

	year_start_date = getdate(fiscal_year.year_start_date)
	year_end_date = getdate(fiscal_year.year_end_date)

	month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov","Dec"].index(filters["month"]) + 1
	month = cint(month)

	period_list = []
	month_list = []

	from_fiscal_year_year_start_date = getdate(from_fiscal_year[1])
	to_fiscal_year_year_start_date = getdate(to_fiscal_year[1])
	from_fiscal_year_year_end_date = getdate(from_fiscal_year[2])
	to_fiscal_year_year_end_date = getdate(to_fiscal_year[2])

	if month > from_fiscal_year_year_start_date.month:
		from_date_period_last_year  = add_months(from_fiscal_year_year_start_date, month - from_fiscal_year_year_start_date.month)
	else:
		from_date_period_last_year  = add_months(from_fiscal_year_year_start_date, 12 + month - from_fiscal_year_year_start_date.month)
	
	if month >= to_fiscal_year_year_start_date.month:
		from_date_period  = add_months(to_fiscal_year_year_start_date, month - to_fiscal_year_year_start_date.month)
		for m in range(0, month - to_fiscal_year_year_start_date.month+1):
			month_list.append(to_fiscal_year_year_start_date.month+m)
	else:
		from_date_period  = add_months(to_fiscal_year_year_start_date, 12 + month - to_fiscal_year_year_start_date.month)
		for m in range(0, 12 + month - to_fiscal_year_year_start_date.month+1):
			if to_fiscal_year_year_start_date.month+m <= 12:
				month_list.append(to_fiscal_year_year_start_date.month+m)
			else:
				month_list.append(to_fiscal_year_year_start_date.month+m-12)

	# to_date
	to_date = add_months(from_date_period, 1)
	if to_date == get_first_day(to_date):
		to_date = add_days(to_date, -1)
	if to_date > to_fiscal_year_year_end_date:
		to_date = to_fiscal_year_year_end_date
	
	to_date_last_year = add_months(from_date_period_last_year, 1)
	if to_date_last_year == get_first_day(to_date_last_year):
		to_date_last_year = add_days(to_date_last_year, -1)
	if to_date_last_year > from_fiscal_year_year_end_date:
		to_date_last_year = from_fiscal_year_year_end_date
	
	period_last_year = frappe._dict({
		'key': 'period_last_year',
		'label': 'Last year period Revenue',
		'from_date': from_date_period_last_year,
		'to_date': to_date_last_year,
		'year_start_date': year_start_date,
		'year_end_date': year_end_date,
		'from_date_fiscal_year_start_date': from_fiscal_year[1],
		'to_date_fiscal_year': from_fiscal_year[0],
	})

	period = frappe._dict({
		'key': 'period',
		'label': 'Period Revenue or Cost',
		'from_date': from_date_period,
		'to_date': to_date, 
		'year_start_date': year_start_date,
		'year_end_date': year_end_date,
		'from_date_fiscal_year_start_date': to_fiscal_year[1],
		'to_date_fiscal_year': to_fiscal_year[0],
	})

	last_ytd = frappe._dict({
		'key': 'last_ytd',
		'label': 'Last year period Revenue',
		'from_date':  from_fiscal_year[1],
		'to_date': to_date_last_year, 
		'year_start_date': year_start_date,
		'year_end_date': year_end_date,
		'from_date_fiscal_year_start_date': from_fiscal_year[1],
		'to_date_fiscal_year': from_fiscal_year[0],
	})

	ytd = frappe._dict({
		'key': 'ytd',
		'label': 'YTD revenue or cost',
		'from_date': to_fiscal_year[1],
		'to_date': to_date, 
		'year_start_date': year_start_date,
		'year_end_date': year_end_date,
		'from_date_fiscal_year_start_date': to_fiscal_year[1],
		'to_date_fiscal_year': to_fiscal_year[0],
	})

	period_list.append(period_last_year)
	period_list.append(period)
	period_list.append(last_ytd)
	period_list.append(ytd)

	income = get_data(filters.company, "Income", "Credit", period_list, filters = filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True, ignore_accumulated_values_for_fy= True)

	expense = get_data(filters.company, "Expense", "Debit", period_list, filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True, ignore_accumulated_values_for_fy= True)

	net_profit_loss = get_net_profit_loss(income, expense, period_list, filters.company, filters.presentation_currency)

	#Budget
	list_budget_distribution = {}
	for d in frappe.db.sql("""select md.name, mdp.month, mdp.percentage_allocation
		from `tabMonthly Distribution Percentage` mdp, `tabMonthly Distribution` md
		where mdp.parent=md.name and md.fiscal_year between %s and %s order by md.fiscal_year""",(filters.from_fiscal_year, filters.to_fiscal_year), as_dict=1):
			list_budget_distribution.setdefault(d.name, {}).setdefault(d.month, flt(d.percentage_allocation))
	
	list_budget = {}
	for d in frappe.db.sql("""
			select b.monthly_distribution, ba.account, ba.budget_amount, b.fiscal_year
			from `tabBudget` b, `tabBudget Account` ba
			where b.name=ba.parent and b.docstatus = 1 and b.fiscal_year = %s
			and b.company=%s
		""",(filters.to_fiscal_year, filters.company), as_dict=True):

		if d.monthly_distribution:
			month_name = datetime.date(2013, month, 1).strftime('%B')
			month_percentage = list_budget_distribution.get(d.monthly_distribution, {}).get(month_name, 0) \
				if d.monthly_distribution else 100.0/12
			
			ytd_budget = 0
			for m in month_list:
				month_name = datetime.date(2013, m, 1).strftime('%B')
				month_percentage = list_budget_distribution.get(d.monthly_distribution, {}).get(month_name, 0) \
					if d.monthly_distribution else 100.0/12
				ytd_budget += flt(d.budget_amount) * month_percentage / 100

			list_budget[d.account] = {
				"period_budget" : flt(d.budget_amount) * month_percentage / 100,
				"ytd_budget" : ytd_budget,
			}
		else:
			list_budget[d.account] = {
				"period_budget" : d.budget_amount,
				"ytd_budget" : d.budget_amount,
			}

	for i in income:
		if i.get("period_last_year") and flt(i["period_last_year"]) > 0:
			i["period_variance"] = (i["period"] - i["period_last_year"])/i["period_last_year"] * 100

		if i.get("account") and  list_budget.get(i["account"]):
			i["ytd_budget"] = list_budget[i["account"]]["ytd_budget"]
		
		if i.get("account") and  list_budget.get(i["account"]):
			i["period_budget"] = list_budget[i["account"]]["period_budget"]		
		
		if i.get("ytd_budget") and flt(i["ytd_budget"]) > 0:
			i["ytd_variance"] = (i["ytd"] - i["ytd_budget"])/i["ytd_budget"] * 100


	for i in expense:
		if i.get("period_last_year") and flt(i["period_last_year"]) > 0:
			i["period_variance"] = (i["period"] - i["period_last_year"])/i["period_last_year"] * 100
		
		if i.get("account") and  list_budget.get(i["account"]):
			i["ytd_budget"] = list_budget[i["account"]]["ytd_budget"]
		
		if i.get("account") and  list_budget.get(i["account"]):
			i["period_budget"] = list_budget[i["account"]]["period_budget"]
		
		if i.get("ytd_budget") and flt(i["ytd_budget"]) > 0:
			i["ytd_variance"] = (i["ytd"] - i["ytd_budget"])/i["ytd_budget"] * 100


	data = []
	data.extend(income or [])
	data.extend(expense or [])
	if net_profit_loss:
		data.append(net_profit_loss)

	columns = get_columns(filters.periodicity, period_list, filters.accumulated_values, filters.company)

	return columns, data, None

def get_net_profit_loss(income, expense, period_list, company, currency=None, consolidated=False):
	total = 0
	net_profit_loss = {
		"account_name": "'" + _("Profit for the year") + "'",
		"account": "'" + _("Profit for the year") + "'",
		"warn_if_negative": True,
		"currency": currency or frappe.get_cached_value('Company',  company,  "default_currency")
	}

	has_value = False

	for period in period_list:
		key = period if consolidated else period.key
		total_income = flt(income[-2][key], 3) if income else 0
		total_expense = flt(expense[-2][key], 3) if expense else 0

		net_profit_loss[key] = total_income - total_expense

		if net_profit_loss[key]:
			has_value=True

		total += flt(net_profit_loss[key])
		net_profit_loss["total"] = total

	if has_value:
		return net_profit_loss
