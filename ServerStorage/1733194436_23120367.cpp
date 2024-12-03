#include <iostream>
#include <algorithm>
#include <queue>
using namespace std;

struct Heap{
	int* arr;
	int capacity;
	int size;
	Heap(int capacity) : arr(new int[capacity]), capacity(capacity), size(0) {}

	~Heap() {
		delete[] arr;
		capacity = 0;
		size = 0;
	}
};
void heapify(Heap* heap, int index) {
	int smallest = index, l = 2 * index + 1, r = 2 * index + 2;
	
	if (l < heap->size && heap->arr[l] < heap->arr[smallest]) smallest = l;
	if (r < heap->size && heap->arr[r] < heap->arr[smallest]) smallest = r;

	if (smallest != index) {
		swap(heap->arr[index], heap->arr[smallest]);
		heapify(heap, smallest);
	}
}
void insert(Heap* heap, int value) {
	if (heap->size >= heap->capacity) {
		cout << "Heap is full\n";
		return;
	}

	int index = heap->size++;
	heap->arr[index] = value;

	while (index > 0 && heap->arr[index] < heap->arr[(index - 1) / 2]) {
		swap(heap->arr[index], heap->arr[(index - 1) / 2]);
		index = (index - 1) / 2;
	}
}
int extractMin(Heap* heap) {
	if (heap->size <= 0) {
		cout << "Heap is empty\n";
		return INT_MAX;
	}
	int res = heap->arr[0];
	
	heap->arr[0] = INT_MAX;
	swap(heap->arr[0], heap->arr[heap->size - 1]);
	heapify(heap, 0);
	heap->size--;

	return res;
}

int getMin(Heap* heap) {
	if (heap->size <= 0) {
		cout << "Heap is empty\n";
		return INT_MAX;
	}

	return heap->arr[0];
}

void deleteKey(Heap* heap, int index) {
	if (index >= heap->size) {
		cout << "Index out of bound\n";
		return;
	}
	
	heap->arr[index] = INT_MIN;
	while (index > 0 && heap->arr[index] < heap->arr[(index - 1) / 2]) {
		swap(heap->arr[index], heap->arr[(index - 1) / 2]);
		index = (index - 1) / 2;
	}
	
	extractMin(heap);
}

int height(Heap* heap) {
	if (heap->size == 0) return 0;
	return log2(heap->size) + 1;
}

void helpPre (Heap *heap, int index) {
	if (index >= heap->size) return;

	cout << heap->arr[index] << ' ';
	helpPre(heap, 2 * index + 1);
	helpPre(heap, 2 * index + 2);
}
void PreOrder(Heap* heap) {
	helpPre(heap, 0);
	cout<<endl;
}
void helpIn (Heap *heap, int index) {
	if (index>=heap->size) return;
	helpIn(heap, 2 * index + 1);
	cout << heap->arr[index] << ' ';
	helpIn(heap, 2 * index + 2);
}
void InOrder(Heap* heap) {
	helpIn(heap, 0);
	cout<<endl;
}
void helpPost (Heap* heap, int index) {
	if (index >= heap->size) return;
    helpPost(heap, 2 * index + 1);
    helpPost(heap, 2 * index + 2);
    cout << heap->arr[index] << ' ';
    return;
}
void PostOrder(Heap* heap) {
	helpPost(heap, 0);
	cout<<endl;
}
void LevelOrder(Heap* heap) {
	queue<int> q;
	q.push(0);
	
	while (!q.empty()) {
		int s = q.size();
		for (int i = 0; i < s; i++) {
			int index = q.front();
			q.pop();
			
			cout << heap->arr[index] << ' ';
			if (2 * index + 1 < heap->size) q.push(2 * index + 1);
			if (2 * index + 2 < heap->size) q.push(2 * index + 2);
		}
		cout << endl;
	}
}
void printAscending(Heap* heap) {
	while (heap->size > 0) {
		cout << extractMin(heap) << ' ';
	}
	cout << endl;
}
int main() {
	Heap* h = new Heap(10);
	insert(h, 20);
	insert(h, 15);
	insert(h, 30);
	insert(h, 10);
	insert(h, 8);
	insert(h, 25);

	cout << "Height: " << height(h) << endl;
	cout<<"Min value: " << extractMin (h)<<endl;

	cout << "\nLevel of order:\n";
	LevelOrder(h);

	cout << "\nPreorder:\n";
	PreOrder(h);

	cout << "\nInorder:\n";
	InOrder(h);

	cout << "\nPostorder:\n";
	PostOrder(h);

	cout << "\nSorted list of elements: ";
	printAscending(h);
	
	delete h;
	return 0;
}