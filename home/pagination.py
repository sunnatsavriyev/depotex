from urllib.parse import urlencode, urlparse, parse_qs, urlunparse
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.exceptions import NotFound


class CustomPagination(PageNumberPagination):
    page_size = 5000000000000000000000000  # default
    # page_size_query_param = None
    # page_query_param = None

    def paginate_queryset(self, queryset, request, view=None):
        self.request = request
        try:
            return super().paginate_queryset(queryset, request, view)
        except NotFound:
            # noto‘g‘ri sahifa bo‘lsa → bo‘sh ro‘yxat qaytadi
            self.page = []
            return []

    def add_extra_params(self, url, request):
        """Frontend yuborgan query paramlarni next/prev urlga qo'shib beradi"""
        if not url:
            return None

        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        # frontenddan kelgan barcha querylarni olish
        for key, value in request.query_params.items():
            if key not in query_params:  # agar qo'shilmagan bo'lsa
                query_params[key] = [value]

        new_query = urlencode(query_params, doseq=True)
        return urlunparse(parsed_url._replace(query=new_query))

    def get_paginated_response(self, data):
        request = self.request

        # agar noto‘g‘ri sahifa bo‘lsa → 0 natija qaytadi
        if self.page == []:
            return Response({
                "count": 0,
                "next": None,
                "previous": None,
                "results": [],
            })

        next_url = self.add_extra_params(self.get_next_link(), request)
        prev_url = self.add_extra_params(self.get_previous_link(), request)

        return Response({
            "count": self.page.paginator.count,
            "next": next_url,
            "previous": prev_url,
            "results": data,
        })
