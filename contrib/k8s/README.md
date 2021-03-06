# Test deployment on minikube

Start minikube:
```
minikube start --memory 4096
```

Set up volumes:
```
kubectl apply -f volumes-minikube.yml
```

Set up services:
```
kubectl apply -f services.yml
```

Set up the configuration:
```
kubectl apply -f config.yml
```

Set up the secrets: (you might want to change the password?)
```
kubectl apply -f secrets
```

Build images locally and load them up in minikube:
```
(cd .. && docker-compose build && docker-compose pull)
../scripts/minikube-load-images.sh
```

Set up Elasticsearch:
```
kubectl apply -f elasticsearch-minikube.yml
```

Set up the deployments:
```
kubectl apply -f deployments.yml
```

You should be able to see Datamart at [`http://192.168.99.100:30080/`](http://192.168.99.100:30080)
