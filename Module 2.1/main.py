import csv
import os.path
import re
from typing import List, Dict, Callable, Iterable
from itertools import groupby
import report


class Salary:
    __currency_to_rub = {
        "AZN": 35.68,
        "BYR": 23.91,
        "EUR": 59.90,
        "GEL": 21.74,
        "KGS": 0.76,
        "KZT": 0.13,
        "RUR": 1,
        "UAH": 1.64,
        "USD": 60.66,
        "UZS": 0.0055,
    }

    def __init__(self, salary_from: str, salary_to: str, salary_currency: str):
        self.salary_from = salary_from[0]
        self.salary_to = salary_to[0]
        self.salary_currency = salary_currency[0]

    def get_middle_salary_rub(self):
        percent = self.__currency_to_rub[self.salary_currency]
        salary_from = int(float(self.salary_from))
        salary_to = int(float(self.salary_to))
        return (salary_from + salary_to) * percent // 2


class Vacancy:
    def __init__(self, name: str, area_name: str, published_at: str, salary_from: str, salary_to: str,
                 salary_currency: str, **not_needed):
        self.name = name[0]
        self.salary = Salary(salary_from, salary_to, salary_currency)
        self.area_name = area_name[0]
        self.published_at = published_at[0]
        self.year = published_at[0].split('-')[0]


class InputConnect:
    @staticmethod
    def get_vacs(grouped: Iterable, by_year: bool = True, need_div: bool = True, default: Dict = None):
        by_count = {}
        by_salary = {}
        if default is not None:
            for k, v in default.items():
                by_count[k] = v
                by_salary[k] = v
        for group, val in grouped:
            by = int(group) if by_year else group
            count = 0
            for v in val:
                count += 1
                if by not in by_count:
                    by_count[by] = 1
                else:
                    by_count[by] += 1
                if by not in by_salary:
                    by_salary[by] = v.salary.get_middle_salary_rub()
                else:
                    by_salary[by] += v.salary.get_middle_salary_rub()
            if need_div and count != 0:
                by_salary[by] = int(by_salary[by] // count)

        return by_count, by_salary

    @staticmethod
    def clear_by_city(salary_by_city, vacancies_by_city, all_count):
        for city in salary_by_city:
            salary = salary_by_city[city]
            salary_by_city[city] = int(salary // vacancies_by_city[city])

        too_small_cities = []
        for city in vacancies_by_city:
            count = vacancies_by_city[city]
            new_value = count / all_count
            if new_value < 0.01:
                too_small_cities.append(city)
            else:
                vacancies_by_city[city] = new_value

        for city in too_small_cities:
            del vacancies_by_city[city]
            del salary_by_city[city]

    @staticmethod
    def print_table(read_csv: Callable) -> Callable:
        def inner(self) -> None:
            csv_generator = read_csv(self)
            next(csv_generator)
            prof_name = input('Введите название профессии: ')
            wkhtml_path = input('Введите путь до wkghml.exe или пустую строку для стандартного пути: ')
            wkhtml_path = os.path.abspath(
                r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe' if wkhtml_path == "" else wkhtml_path)
            vacancies = [v for v in csv_generator]
            vacancies_with_prof = list(filter(lambda v: prof_name in v.name, vacancies))
            vacs_by_year = groupby(vacancies, lambda v: v.year)
            profs_by_year = groupby(vacancies_with_prof, lambda v: v.year)
            vacs_by_city = groupby(vacancies, lambda v: v.area_name)

            vacancies_by_year, salary_by_year = InputConnect.get_vacs(vacs_by_year)
            professions_by_year, profs_salary_by_year = InputConnect.get_vacs(profs_by_year,
                                                                              default={int(k): 0 for k in
                                                                                       vacancies_by_year})

            vacancies_by_city, salary_by_city = InputConnect.get_vacs(vacs_by_city, False, False)
            InputConnect.clear_by_city(salary_by_city, vacancies_by_city, len(vacancies))

            vacancies_by_city_to_print = {k: float('{:.4f}'.format(v)) for k, v in sorted(vacancies_by_city.items(),
                                                                                          key=lambda item: item[1],
                                                                                          reverse=True)[:10]}
            salary_by_city_to_print = {k: v for k, v in
                                       sorted(salary_by_city.items(), key=lambda item: item[1], reverse=True)[:10]}

            print('Динамика уровня зарплат по годам:', salary_by_year)
            print('Динамика количества вакансий по годам:', vacancies_by_year)
            print('Динамика уровня зарплат по годам для выбранной профессии:', profs_salary_by_year)
            print('Динамика количества вакансий по годам для выбранной профессии:', professions_by_year)
            print('Уровень зарплат по городам (в порядке убывания):',
                  salary_by_city_to_print)
            print('Доля вакансий по городам (в порядке убывания):',
                  vacancies_by_city_to_print)

            rep = report.Report(salary_by_city_to_print, vacancies_by_city_to_print, salary_by_year, vacancies_by_year,
                                profs_salary_by_year, professions_by_year, prof_name)
            rep.generate_excel()
            rep.generate_image()
            rep.generate_pdf(wkhtml_path)

        return inner


class DataSet:
    def __init__(self):
        self.file_name = None
        self.vacancies_objects: List[Vacancy] = []
        self.__RE_ALL_HTML = re.compile(r'<.*?>')
        self.__RE_ALL_NEWLINE = re.compile(r'\n|\r\n')
        self.__header: List[str] = []

    @InputConnect.print_table
    def read_csv(self) -> Vacancy or []:
        self.file_name = input('Введите название файла: ')
        with open(self.file_name, encoding="utf-8") as file:
            header = []
            file_reader = csv.reader(file)
            columns_count = 0
            for row in file_reader:
                header = row
                header[0] = 'name'
                self.__header = header
                columns_count = len(row)
                break
            yield header
            for row in file_reader:
                if "" in row or len(row) < columns_count:
                    continue
                cleared = self.__clear_field(row)
                vacancy = Vacancy(**cleared)
                self.vacancies_objects.append(vacancy)
                yield vacancy
            if len(self.vacancies_objects) == 0:
                yield
            else:
                return []

    def __clear_field(self, items: List[str]) -> Dict[str, List[str]]:
        field = {}
        for column, row in zip(self.__header, items):
            field[column] = list(map(self.__delete_html, self.__split_by_newline(row)))
        return field

    def __delete_html(self, item: str) -> str:
        return " ".join(re.
                        sub(self.__RE_ALL_HTML, "", item)
                        .split())

    def __split_by_newline(self, item: str) -> List[str]:
        return re.split(self.__RE_ALL_NEWLINE, item)


reader = DataSet()
reader.read_csv()
