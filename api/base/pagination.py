from django.utils import six
from collections import OrderedDict
from django.core.urlresolvers import reverse
from django.core.paginator import InvalidPage, Paginator as DjangoPaginator

from rest_framework import pagination
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.utils.urls import (
    replace_query_param, remove_query_param
)

class JSONAPIPagination(pagination.PageNumberPagination):
    """Custom paginator that formats responses in a JSON-API compatible format."""

    page_size_query_param = 'page[size]'

    def get_first_link(self):
        if not self.page.has_previous():
            return None
        url = self.request.build_absolute_uri()
        return remove_query_param(url, self.page_query_param)

    def get_last_link(self):
        if not self.page.has_next():
            return None
        url = self.request.build_absolute_uri()
        page_number = self.page.paginator.num_pages
        return replace_query_param(url, self.page_query_param, page_number)

    def get_paginated_response(self, data):
        response_dict = OrderedDict([
            ('data', data),
            ('links', OrderedDict([
                ('first', self.get_first_link()),
                ('last', self.get_last_link()),
                ('prev', self.get_previous_link()),
                ('next', self.get_next_link()),
                ('meta', OrderedDict([
                    ('total', self.page.paginator.count),
                    ('per_page', self.page.paginator.per_page),
                ]))
            ])),
        ])
        return Response(response_dict)


class EmbeddedPagination(JSONAPIPagination):

    def page_number_query(self, url, page_number):
        """
        Adds page param to paginated urls.
        """

        url = replace_query_param(url, self.page_query_param, page_number)

        if page_number == 1:
            return remove_query_param(url, self.page_query_param)

        return url

    def get_first_real_link(self, url):
        if not self.page.has_previous():
            return None
        return self.page_number_query(self.request.build_absolute_uri(url), 1)

    def get_last_real_link(self, url):
        if not self.page.has_next():
            return None
        url = self.request.build_absolute_uri(url)
        page_number = self.page.paginator.num_pages
        return self.page_number_query(url, page_number)

    def get_previous_real_link(self, url):
        if not self.page.has_previous():
            return None
        url = self.request.build_absolute_uri(url)
        page_number = self.page.previous_page_number()
        return self.page_number_query(url, page_number)

    def get_next_real_link(self, url):
        if not self.page.has_next():
            return None
        url = self.request.build_absolute_uri(url)
        page_number = self.page.next_page_number()
        return self.page_number_query(url, page_number)

    def get_paginated_response(self, data):
        """
        Formats paginated response in accordance with JSON API.

        Creates pagination links from the view_name if embedded resource,
        rather than the location used in the request.
        """
        kwargs = self.request.parser_context['kwargs'].copy()
        embedded = kwargs.pop('no_embeds', None)
        view_name = self.request.parser_context['view'].view_name
        reversed_url = None
        if embedded:
            reversed_url = reverse(view_name, kwargs=kwargs)

        response_dict = OrderedDict([
            ('data', data),
            ('links', OrderedDict([
                ('first', self.get_first_real_link(reversed_url)),
                ('last', self.get_last_real_link(reversed_url)),
                ('prev', self.get_previous_real_link(reversed_url)),
                ('next', self.get_next_real_link(reversed_url)),
                ('meta', OrderedDict([
                    ('total', self.page.paginator.count),
                    ('per_page', self.page.paginator.per_page),
                ]))
            ])),
        ])
        return Response(response_dict)

    def paginate_queryset(self, queryset, request, view=None):
        """
        Custom pagination of queryset. Returns page object or `None` if not configured for view.

        If this is an embedded resource, returns first page, ignoring query params.
        """
        if request.parser_context['kwargs'].get('no_embeds'):
            self._handle_backwards_compat(view)
            page_size = self.get_page_size(request)
            if not page_size:
                return None
            paginator = DjangoPaginator(queryset, page_size)
            page_number = 1
            try:
                self.page = paginator.page(page_number)
            except InvalidPage as exc:
                msg = self.invalid_page_message.format(
                    page_number=page_number, message=six.text_type(exc)
                )
                raise NotFound(msg)

            if paginator.count > 1 and self.template is not None:
                # The browsable API should display pagination controls.
                self.display_page_controls = True

            self.request = request
            return list(self.page)

        else:
            return super(EmbeddedPagination, self).paginate_queryset(queryset, request, view=None)
