# -*- coding: utf-8 -*-
from operator import and_
from operator import or_

from elasticutils import F
from elasticutils import Q
from elasticutils.contrib.django import S as _S

from rest_framework.filters import SearchFilter


class S(_S):

    def all(self):
        for r in self.execute():
            yield r.get_object()


class ElasticutilsFilterSet(object):

    def __init__(self, search_fields=None, search_actions=None,
                 search_terms=None, mapping_type=None, queryset=None):

        self.search_fields = search_fields or ['_all']
        self.search_actions = search_actions or {}
        self.search_terms = search_terms or {'_all': ''}

        self.mapping_type = mapping_type
        self.queryset = queryset

    def __iter__(self):
        for obj in self.qs:
            yield obj

    def __len__(self):
        return self.count()

    def __getitem__(self, key):
        return self.qs[key]

    @property
    def qs(self):
        query = self.queryset or Q()
        filter_ = F()
        term = self.search_terms.get('_all')
        operation = or_ if term else and_
        for f in self.search_fields:
            action = self.search_actions.get(f, '')
            field_action = '{0}__{1}'.format(f, action)
            term = term or self.search_terms.get(f)
            # nothing to filter on
            if not term:
                continue
            # update query
            filter_ = operation(filter_, F(**{field_action: term}))
        return S(self.mapping_type).query(query).filter(filter_)

    @property
    def count(self):
        return self.qs.count()

    @property
    def form(self):
        raise NotImplemented('Form not yet implemented')

    def get_ordering_field(self):
        raise NotImplemented('Form not yet implemented')

    @property
    def ordering_field(self):
        if not hasattr(self, '_ordering_field'):
            self._ordering_field = self.get_ordering_field()
        return self._ordering_field

    def get_order_by(self, order_choice):
        return [order_choice]

    @classmethod
    def filter_for_field(cls, f, name):
        raise NotImplemented('Form not yet implemented')

    @classmethod
    def filter_for_reverse_field(cls, f, name):
        raise NotImplemented('Form not yet implemented')


class ElasticutilsFilterBackend(SearchFilter):

    key_separator = ':'
    query_splitter = ' '

    def get_filter_class(self, view, queryset=None):
        return getattr(view, 'filter_class', ElasticutilsFilterSet)

    def get_filter_key(self, view, queryset=None):
        return getattr(view, 'filter_key', 'q')

    def split_query_str(self, query_str):
        """
        >>> self.split_query_str('helo')
        {'_all': 'helo'}

        >>> self.split_query_str('firstname:bob lastname:dylan')
        {'firstname': 'bob', 'lastname': 'dylan'}
        """
        # little cleaning
        query_str = query_str.strip()

        if self.key_separator not in query_str:
            return {'_all': query_str}

        return dict([s.strip().split(self.key_separator)
                     for s in query_str.split(self.query_splitter)])

    def get_search_terms(self, request, view, queryset=None):
        """Return Splitted query string automagically.
        """
        filter_key = self.get_filter_key(view)
        query_str = request.QUERY_PARAMS.get(filter_key, '')
        return self.split_query_str(query_str)

    def filter_queryset(self, request, queryset, view):

        search_terms = self.get_search_terms(request, view, queryset)
        search_actions = getattr(view, 'search_actions', None)
        search_fields = getattr(view, 'search_fields', search_terms.keys())

        mapping_type = getattr(view, 'mapping_type', None)

        filter_class = self.get_filter_class(view, queryset)

        return filter_class(search_fields=search_fields,
                            search_actions=search_actions,
                            search_terms=search_terms,
                            mapping_type=mapping_type,
                            queryset=queryset).qs