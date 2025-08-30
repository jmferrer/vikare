make: build deploy

build:
	docker build . --push -t localhost:32000/vikare

deploy:
	helm upgrade --install vikare --namespace vikare --create-namespace helm
	kubectl -n vikare scale --replicas=0 statefulset/vikare
	kubectl -n vikare scale --replicas=1 statefulset/vikare

logs:
	kubectl -n vikare logs vikare-0 -c llm
	kubectl -n vikare logs vikare-0 -c image
	kubectl -n vikare logs vikare-0 -c sensors
