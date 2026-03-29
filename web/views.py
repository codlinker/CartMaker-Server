from django.shortcuts import render
from rest_framework.views import View

class Home(View):
    """
    Endpoint principal
    """
    
    def get(self, request):
        return render(request, 'index.html')
