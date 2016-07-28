from website.project.taxonomies import Subject

from rest_framework import generics, permissions as drf_permissions

from api.taxonomies.serializers import TaxonomySerializer
from api.base.views import JSONAPIBaseView
from modularodm import Q

class PlosTaxonomy(JSONAPIBaseView, generics.ListAPIView):
    '''[PLOS taxonomy of subjects](http://journals.plos.org/plosone/browse/) in flattened form. *Read-only*

    ##Taxonomy Attributes

        name           type                   description
        ----------------------------------------------------------------------------
        data           array of subjects      List of subjects

    Each subject is represented by an object with the following fields:

    * 'id' - autogenerated id of subject
    * `text` - a string that is the subject itself
    * `parent_id` - id of the parent subject
    * `type` - in this case the string `'plos'`

    Only the top three levels of the PLOS taxonomy are included.
    '''
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
    )

    serializer_class = TaxonomySerializer
    view_category = 'plos-taxonomies'
    view_name = 'plos-taxonomy'

    # overrides ListAPIView
    def get_queryset(self):
        subjects = Subject.find(
            Q('type', 'eq', 'plos')
        )
        return subjects
